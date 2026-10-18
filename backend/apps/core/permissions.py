"""
Role-based permission classes.

These run on the server for every request, so hiding a button in React is only
a convenience: the API itself refuses actions a role is not allowed to take.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


def _role(request):
    user = request.user
    return getattr(user, "role", None) if user and user.is_authenticated else None


class IsAdminRole(BasePermission):
    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return _role(request) == "ADMIN"


class IsStaffRole(BasePermission):
    """Admins and agents."""

    message = "Only support staff can perform this action."

    def has_permission(self, request, view):
        return _role(request) in ("ADMIN", "AGENT")


class IsCustomerRole(BasePermission):
    message = "Only customers can perform this action."

    def has_permission(self, request, view):
        return _role(request) == "CUSTOMER"


class ReadOnlyOrAdmin(BasePermission):
    """Any authenticated user can read; only admins can write."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return _role(request) == "ADMIN"


class StaffReadOnlyOrAdmin(BasePermission):
    """Staff can read; only admins can write."""

    def has_permission(self, request, view):
        role = _role(request)
        if request.method in SAFE_METHODS:
            return role in ("ADMIN", "AGENT")
        return role == "ADMIN"
