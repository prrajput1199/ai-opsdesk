from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import Team, User


class TeamSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Team
        fields = ["id", "name", "description", "member_count", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal public representation used inside tickets and messages."""

    name = serializers.CharField(source="full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "role"]


class MeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name", read_only=True)
    team = TeamSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "name", "role", "team", "date_joined", "last_login"]
        read_only_fields = ["id", "email", "role", "team", "date_joined", "last_login"]


class RegisterSerializer(serializers.Serializer):
    """Public registration. The role is always CUSTOMER and cannot be chosen by the client."""

    email = serializers.EmailField(max_length=254)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=128, style={"input_type": "password"})

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        candidate = User(email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"])
        password_validation.validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(role=User.Role.CUSTOMER, **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, style={"input_type": "password"})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, max_length=128)
    new_password = serializers.CharField(write_only=True, max_length=128)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate(self, attrs):
        password_validation.validate_password(attrs["new_password"], user=self.context["request"].user)
        return attrs


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------
STAFF_ROLES = [User.Role.AGENT, User.Role.ADMIN]


class UserAdminSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name", read_only=True)
    team = TeamSerializer(read_only=True)
    open_ticket_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "name", "role", "team", "is_active",
            "date_joined", "last_login", "open_ticket_count",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Admins create staff accounts (agents or other admins)."""

    role = serializers.ChoiceField(choices=STAFF_ROLES)
    team_id = serializers.PrimaryKeyRelatedField(
        source="team", queryset=Team.objects.all(), required=False, allow_null=True
    )
    password = serializers.CharField(write_only=True, max_length=128)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role", "team_id", "password"]
        extra_kwargs = {"first_name": {"required": True}, "last_name": {"required": True}}

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        candidate = User(email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"])
        password_validation.validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    team_id = serializers.PrimaryKeyRelatedField(
        source="team", queryset=Team.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "role", "team_id", "is_active"]

    def validate(self, attrs):
        instance = self.instance
        actor = self.context["request"].user
        new_role = attrs.get("role", instance.role)
        if instance.role == User.Role.CUSTOMER and new_role != User.Role.CUSTOMER:
            raise serializers.ValidationError({"role": "Customer accounts cannot be promoted to staff."})
        if instance.role != User.Role.CUSTOMER and new_role == User.Role.CUSTOMER:
            raise serializers.ValidationError({"role": "Staff accounts cannot be converted to customers."})
        if instance.pk == actor.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "You cannot deactivate your own account."})
            if new_role != instance.role:
                raise serializers.ValidationError({"role": "You cannot change your own role."})
        return attrs


class AgentDirectorySerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name", read_only=True)
    team_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "team_id"]
