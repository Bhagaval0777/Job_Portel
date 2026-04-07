from rest_framework.permissions import BasePermission
from .models import RolePermission



class HasResourcePermission(BasePermission):


    def __init__(self, resource: str, action: str):

        self.resource = resource
        self.action   = action

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = getattr(request.user, "role", None)
        if not role:
            return False

        # Admin bypasses the table — full access to everything
        if role == "admin":
            return True

        try:
            perm = RolePermission.objects.get(
                role=role,
                resource=self.resource
            )
            return getattr(perm, self.action, False)
        except RolePermission.DoesNotExist:
            return False




class IsAdmin(BasePermission):
    """Allow only Admin users."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "admin"


class IsRecruiter(BasePermission):
    """Allow only Recruiter users."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "recruiter"


class IsJobSeeker(BasePermission):
    """Allow only JobSeeker users."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "jobseeker"


# ── Combinations ──────────────────────────────────────────────────────────────

class IsAdminOrRecruiter(BasePermission):
    """Allow Admin or Recruiter — e.g. viewing applicants."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) in ["admin", "recruiter"]


class IsAdminOrJobSeeker(BasePermission):
    """Allow Admin or JobSeeker — e.g. managing resumes."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) in ["admin", "jobseeker"]


class IsAuthenticatedUser(BasePermission):
    """Any logged in user regardless of role — e.g. viewing notifications."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)