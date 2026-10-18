import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditLog

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register/"
LOGIN = "/api/v1/auth/login/"
ME = "/api/v1/auth/me/"
REFRESH = "/api/v1/auth/refresh/"
LOGOUT = "/api/v1/auth/logout/"


def _register_payload(**overrides):
    data = {"email": "New.User@Example.com", "first_name": "New", "last_name": "User", "password": PASSWORD}
    data.update(overrides)
    return data


def test_register_creates_customer_and_sets_httponly_cookies():
    client = APIClient()
    res = client.post(REGISTER, _register_payload(), format="json")
    assert res.status_code == 201
    assert res.data["role"] == "CUSTOMER"
    assert res.data["email"] == "new.user@example.com"
    access = res.cookies[settings.AUTH_COOKIE_ACCESS]
    refresh = res.cookies[settings.AUTH_COOKIE_REFRESH]
    assert access["httponly"] and refresh["httponly"]
    assert refresh["path"] == settings.AUTH_COOKIE_REFRESH_PATH
    assert "access" not in res.data and "refresh" not in res.data  # tokens never in the JSON body
    assert AuditLog.objects.filter(action=AuditAction.REGISTER).exists()


def test_register_ignores_role_in_payload():
    res = APIClient().post(REGISTER, _register_payload(role="ADMIN", is_staff=True), format="json")
    assert res.status_code == 201
    user = User.objects.get(email="new.user@example.com")
    assert user.role == User.Role.CUSTOMER and not user.is_staff


def test_register_rejects_weak_password_and_duplicate_email(customer):
    res = APIClient().post(REGISTER, _register_payload(password="12345678"), format="json")
    assert res.status_code == 400
    res = APIClient().post(REGISTER, _register_payload(email="CUSTOMER@example.com"), format="json")
    assert res.status_code == 400 and "email" in res.data


def test_login_success_and_cookie_authenticates_me(customer):
    client = APIClient()
    res = client.post(LOGIN, {"email": "Customer@Example.com", "password": PASSWORD}, format="json")
    assert res.status_code == 200
    assert res.data["email"] == customer.email
    me = client.get(ME)  # the access cookie set by login is sent automatically
    assert me.status_code == 200 and me.data["role"] == "CUSTOMER"


def test_login_failure_is_generic_and_audited(customer):
    res = APIClient().post(LOGIN, {"email": customer.email, "password": "wrong-password"}, format="json")
    assert res.status_code == 401
    assert res.data["detail"] == "Invalid email or password."
    assert AuditLog.objects.filter(action=AuditAction.LOGIN_FAILED, metadata__email=customer.email).exists()


def test_inactive_user_cannot_log_in(customer):
    customer.is_active = False
    customer.save()
    res = APIClient().post(LOGIN, {"email": customer.email, "password": PASSWORD}, format="json")
    assert res.status_code == 401


def test_protected_endpoint_requires_authentication():
    assert APIClient().get(ME).status_code == 401
    assert APIClient().get("/api/v1/tickets/").status_code == 401


def test_invalid_access_cookie_is_rejected():
    client = APIClient()
    client.cookies[settings.AUTH_COOKIE_ACCESS] = "not-a-jwt"
    assert client.get(ME).status_code == 401


def test_refresh_rotates_tokens_and_logout_revokes(customer):
    client = APIClient()
    client.post(LOGIN, {"email": customer.email, "password": PASSWORD}, format="json")
    old_refresh = client.cookies[settings.AUTH_COOKIE_REFRESH].value

    res = client.post(REFRESH)
    assert res.status_code == 200
    new_refresh = res.cookies[settings.AUTH_COOKIE_REFRESH].value
    assert new_refresh != old_refresh

    # The old refresh token was blacklisted on rotation.
    replay = APIClient()
    replay.cookies[settings.AUTH_COOKIE_REFRESH] = old_refresh
    assert replay.post(REFRESH).status_code == 401

    assert client.post(LOGOUT).status_code == 205
    replay.cookies[settings.AUTH_COOKIE_REFRESH] = new_refresh
    assert replay.post(REFRESH).status_code == 401


def test_refresh_without_cookie_returns_401():
    assert APIClient().post(REFRESH).status_code == 401


def test_csrf_is_enforced_for_cookie_authenticated_writes(customer, categories):
    client = APIClient(enforce_csrf_checks=True)
    token = client.get("/api/v1/auth/csrf/").data["csrfToken"]
    res = client.post(LOGIN, {"email": customer.email, "password": PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token)
    assert res.status_code == 200

    payload = {"title": "Something broke", "description": "A long enough description of the issue."}
    assert client.post("/api/v1/tickets/", payload, format="json").status_code == 403  # missing header
    res = client.post("/api/v1/tickets/", payload, format="json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
    assert res.status_code == 201


def test_login_requires_csrf_token(customer):
    client = APIClient(enforce_csrf_checks=True)
    res = client.post(LOGIN, {"email": customer.email, "password": PASSWORD}, format="json")
    assert res.status_code == 403


def test_change_password_revokes_other_sessions(customer):
    client = APIClient()
    client.post(LOGIN, {"email": customer.email, "password": PASSWORD}, format="json")
    other_device_refresh = client.cookies[settings.AUTH_COOKIE_REFRESH].value

    res = client.post("/api/v1/auth/change-password/",
                      {"current_password": PASSWORD, "new_password": "An0ther-Strong!Pass"}, format="json")
    assert res.status_code == 200
    other = APIClient()
    other.cookies[settings.AUTH_COOKIE_REFRESH] = other_device_refresh
    assert other.post(REFRESH).status_code == 401
    customer.refresh_from_db()
    assert customer.check_password("An0ther-Strong!Pass")


def test_change_password_requires_current_password(customer, api):
    res = api(customer).post("/api/v1/auth/change-password/",
                             {"current_password": "wrong", "new_password": "An0ther-Strong!Pass"}, format="json")
    assert res.status_code == 400


def test_profile_update_cannot_change_role(customer, api):
    res = api(customer).patch(ME, {"first_name": "Renamed", "role": "ADMIN", "email": "x@y.com"}, format="json")
    assert res.status_code == 200
    customer.refresh_from_db()
    assert customer.first_name == "Renamed"
    assert customer.role == "CUSTOMER" and customer.email == "customer@example.com"


def test_login_is_rate_limited(customer):
    client = APIClient()
    codes = [client.post(LOGIN, {"email": customer.email, "password": "bad"}, format="json").status_code
             for _ in range(12)]
    assert 429 in codes
