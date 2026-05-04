from rest_framework.permissions import BasePermission
from .models import RolePermission


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 1 — Basic Role Checks
# Fastest checks — no DB hit, just reads role from token
# ─────────────────────────────────────────────────────────────────────────────

class IsRecruiter(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "recruiter"


class IsJobSeeker(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) == "jobseeker"


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 2 — Role Combinations
# For endpoints shared between multiple roles
# No DB hit — just reads role from token
# ─────────────────────────────────────────────────────────────────────────────

class IsAdminOrRecruiter(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "is_staff", False) or \
            getattr(request.user, "role", None) == "recruiter"


class IsAdminOrJobSeeker(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "is_staff", False) or getattr(request.user, "role", None) == "jobseeker"


class IsRecruiterOrJobSeeker(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", None) in ["recruiter", "jobseeker"]



class IsOwner(BasePermission):

    def __init__(self, owner_field="user"):
        self.owner_field = owner_field

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, self.owner_field, None)
        if owner is None:
            return False
        # handle both FK object and raw id
        if hasattr(owner, "pk"):
            return owner.pk == request.user.pk
        return owner == request.user.pk

class IsOwnerOrAdmin(BasePermission):

    def __init__(self, owner_field="user"):
        self.owner_field = owner_field

    def has_object_permission(self, request, view, obj):
        # admin bypasses ownership check
        if getattr(request.user, "is_staff", False):
            return True
        owner = getattr(obj, self.owner_field, None)
        if owner is None:
            return False
        if hasattr(owner, "pk"):
            return owner.pk == request.user.pk
        return owner == request.user.pk

class IsVerifiedUser(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "is_verified", False) is True


class IsActiveUser(BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "is_active", False) is True



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

        # admin bypasses table — full access to everything
        if getattr(request.user, "is_staff", False):
            return True

        try:
            perm = RolePermission.objects.get(
                role=role,
                resource=self.resource
            )
            return getattr(perm, self.action, False)
        except RolePermission.DoesNotExist:
            return False

