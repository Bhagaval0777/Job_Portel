import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import RolePermission
from rest_framework.permissions import IsAdminUser

from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

class UserLogin(APIView):
    def post(self, request):
        email = request.data.get("user_email")
        password = request.data.get("password")

        user = authenticate(username=email, password=password)

        if user is None:
            return Response({"error": "Invalid credentials"}, status=401)

        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
        })
class RoleAccessView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ✅ 1. ADMIN FIRST
        if user.is_staff:
            permissions = self._admin_full_access()
            role = None  # optional, just for response

        else:
            # ✅ 2. THEN role-based logic
            role = getattr(user, "role", None)

            if not role:
                return Response(
                    {"error": "user has no role assigned."},
                    status=status.HTTP_403_FORBIDDEN
                )

            permissions = self._get_permissions_from_db(role)

        logger.info("ROLE_ACCESS | user=%s | role=%s", user.user_id, role)

        return Response({
            "user_id": user.user_id,
            "email": user.user_email,
            "role": role,
            "permissions": permissions,
        }, status=status.HTTP_200_OK)

    def _get_permissions_from_db(self, role: str) -> dict:

        rows = RolePermission.objects.filter(role=role)
        return {
            row.resource: {
                "can_read":   row.can_read,
                "can_write":  row.can_write,
                "can_delete": row.can_delete,
            }
            for row in rows
        }

    def _admin_full_access(self) -> dict:

        resources = [
            "jobs", "resume", "applications",
            "user", "company", "messages",
            "notifications", "subscriptions"
        ]
        return {
            resource: {"can_read": True, "can_write": True, "can_delete": True}
            for resource in resources
        }


class RolePermissionListView(APIView):

    permission_classes = [IsAdminUser]

    def get(self, request):
        rows = RolePermission.objects.all()
        data = [
            {
                "id":         row.id,
                "role":       row.role,
                "resource":   row.resource,
                "can_read":   row.can_read,
                "can_write":  row.can_write,
                "can_delete": row.can_delete,
            }
            for row in rows
        ]
        return Response({"permissions": data}, status=status.HTTP_200_OK)


class RolePermissionUpdateView(APIView):

    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            perm = RolePermission.objects.get(pk=pk)
        except RolePermission.DoesNotExist:
            return Response(
                {"error": "Permission row not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        perm.can_read   = request.data.get("can_read",   perm.can_read)
        perm.can_write  = request.data.get("can_write",  perm.can_write)
        perm.can_delete = request.data.get("can_delete", perm.can_delete)
        perm.save()

        logger.info(
            "PERMISSION_UPDATE | admin=%s | perm_id=%s | role=%s | resource=%s",
            request.user.user_id, perm.id, perm.role, perm.resource
        )

        return Response({
            "message":    "Permission updated successfully.",
            "id":         perm.id,
            "role":       perm.role,
            "resource":   perm.resource,
            "can_read":   perm.can_read,
            "can_write":  perm.can_write,
            "can_delete": perm.can_delete,
        }, status=status.HTTP_200_OK)