import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.db.models import Count, Q
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditAction
from apps.audit.services import log_action
from apps.core.permissions import IsAdminRole, IsStaffRole, StaffReadOnlyOrAdmin

from .authentication import enforce_csrf
from .cookies import clear_auth_cookies, set_auth_cookies
from .models import Team, User
from .serializers import (
    AgentDirectorySerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    MeSerializer,
    RegisterSerializer,
    TeamSerializer,
    UserAdminSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
)

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ["OPEN", "IN_PROGRESS", "WAITING_FOR_CUSTOMER"]


def _issue_tokens(response, user):
    refresh = RefreshToken.for_user(user)
    set_auth_cookies(response, refresh.access_token, refresh)
    update_last_login(None, user)
    return response


def revoke_all_refresh_tokens(user):
    """Blacklist every outstanding refresh token (logout everywhere)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class PublicAuthView(APIView):
    """
    Base for login/register/refresh/logout. These endpoints must not try to authenticate an
    (expired) access cookie, but they still enforce CSRF to prevent login-CSRF attacks.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            enforce_csrf(request)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(PublicAuthView):
    throttle_classes = []

    @extend_schema(responses=inline_serializer("CsrfToken", {"csrfToken": serializers.CharField()}), auth=[])
    def get(self, request):
        """Returns a CSRF token (also set as the `csrftoken` cookie). Send it as X-CSRFToken."""
        return Response({"csrfToken": get_token(request)})


class RegisterView(PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(request=RegisterSerializer, responses={201: MeSerializer}, auth=[])
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        log_action(AuditAction.REGISTER, actor=user, target=user, description="Customer registered", request=request)
        response = Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)
        return _issue_tokens(response, user)


class LoginView(PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer, 401: OpenApiResponse(description="Invalid credentials")}, auth=[])
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = authenticate(request, email=email, password=serializer.validated_data["password"])
        if user is None:  # wrong password, unknown email or inactive account: same message for all
            log_action(AuditAction.LOGIN_FAILED, description="Failed login attempt", metadata={"email": email}, request=request)
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        log_action(AuditAction.LOGIN, actor=user, target=user, description="Logged in", request=request)
        return _issue_tokens(Response(MeSerializer(user).data), user)


class RefreshView(PublicAuthView):
    throttle_classes = []

    @extend_schema(request=None, responses={200: inline_serializer("RefreshOk", {"detail": serializers.CharField()})}, auth=[])
    def post(self, request):
        """Rotates the refresh cookie and issues a new access cookie."""
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw:
            return clear_auth_cookies(Response({"detail": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED))
        serializer = TokenRefreshSerializer(data={"refresh": raw})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken, AuthenticationFailed, serializers.ValidationError) as exc:
            logger.info("Refresh rejected: %s", exc.__class__.__name__)
            return clear_auth_cookies(
                Response({"detail": "Session expired. Please log in again."}, status=status.HTTP_401_UNAUTHORIZED)
            )
        data = serializer.validated_data
        response = Response({"detail": "Token refreshed."})
        return set_auth_cookies(response, data["access"], data.get("refresh"))


class LogoutView(PublicAuthView):
    throttle_classes = []

    @extend_schema(request=None, responses={205: None}, auth=[])
    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        actor = None
        if raw:
            try:
                token = RefreshToken(raw)
                actor = User.objects.filter(pk=token.get("user_id")).first()
                token.blacklist()
            except TokenError:
                pass
        if actor:
            log_action(AuditAction.LOGOUT, actor=actor, target=actor, description="Logged out", request=request)
        return clear_auth_cookies(Response(status=status.HTTP_205_RESET_CONTENT))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeSerializer, responses=MeSerializer)
    def patch(self, request):
        serializer = MeSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=ChangePasswordSerializer, responses={200: inline_serializer("PasswordChanged", {"detail": serializers.CharField()})})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        revoke_all_refresh_tokens(user)  # sign out every other device
        log_action(AuditAction.PASSWORD_CHANGED, actor=user, target=user, description="Changed password", request=request)
        return _issue_tokens(Response({"detail": "Password updated."}), user)


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Admin user management. Users are deactivated, never deleted, so history stays intact."""

    permission_classes = [IsAdminRole]
    filterset_fields = ["role", "is_active", "team"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["email", "date_joined", "last_login", "open_ticket_count"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return User.objects.select_related("team").annotate(
            open_ticket_count=Count("assigned_tickets", filter=Q(assigned_tickets__status__in=ACTIVE_STATUSES))
        ).order_by("email")

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserAdminSerializer

    @extend_schema(responses={201: UserAdminSerializer})
    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        log_action(AuditAction.USER_CREATED, actor=request.user, target=user,
                   description=f"Created {user.role.lower()} {user.email}", request=request)
        return Response(UserAdminSerializer(self.get_queryset().get(pk=user.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=UserAdminSerializer)
    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        was_active = user.is_active
        changed = {k: str(v) for k, v in serializer.validated_data.items()}
        serializer.save()
        if was_active and not user.is_active:
            revoke_all_refresh_tokens(user)
            log_action(AuditAction.USER_DEACTIVATED, actor=request.user, target=user,
                       description=f"Deactivated {user.email}", request=request)
        elif not was_active and user.is_active:
            log_action(AuditAction.USER_ACTIVATED, actor=request.user, target=user,
                       description=f"Activated {user.email}", request=request)
        else:
            log_action(AuditAction.USER_UPDATED, actor=request.user, target=user,
                       description=f"Updated {user.email}", metadata={"fields": changed}, request=request)
        return Response(UserAdminSerializer(self.get_queryset().get(pk=user.pk)).data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class AgentDirectoryView(APIView):
    """Active agents and admins, for assignment dropdowns and filters (staff only)."""

    permission_classes = [IsStaffRole]

    @extend_schema(responses=AgentDirectorySerializer(many=True))
    def get(self, request):
        agents = User.objects.filter(is_active=True, role__in=[User.Role.AGENT, User.Role.ADMIN]).order_by(
            "first_name", "last_name"
        )
        return Response(AgentDirectorySerializer(agents, many=True).data)


class TeamViewSet(viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    permission_classes = [StaffReadOnlyOrAdmin]
    pagination_class = None
    search_fields = ["name"]

    def get_queryset(self):
        return Team.objects.annotate(member_count=Count("members", filter=Q(members__is_active=True))).order_by("name")

    def perform_create(self, serializer):
        team = serializer.save()
        log_action(AuditAction.TEAM_CHANGED, actor=self.request.user, target=team,
                   description=f"Created team {team.name}", request=self.request)

    def perform_update(self, serializer):
        team = serializer.save()
        log_action(AuditAction.TEAM_CHANGED, actor=self.request.user, target=team,
                   description=f"Updated team {team.name}", request=self.request)

    def perform_destroy(self, instance):
        log_action(AuditAction.TEAM_CHANGED, actor=self.request.user, target=instance,
                   description=f"Deleted team {instance.name}", request=self.request)
        instance.delete()
