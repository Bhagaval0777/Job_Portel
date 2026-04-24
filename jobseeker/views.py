from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render

import logging
from django.db import IntegrityError

from .models import JobSeekerProfile
from .serializers import JobSeekerProfileSerializer

logger = logging.getLogger(__name__)

def profile(request):
    return render(request, 'profile.html')

class JobSeekerProfileAPIView(APIView):

    # 🔹 GET PROFILE
    def get(self, request):

        try:
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return Response(
                    {"message": "Profile not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = JobSeekerProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'JobSeekerProfile GET error for user {request.user.id}: {e}', exc_info=True)
            return Response(
                {"error": "Something went wrong"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # 🔹 CREATE PROFILE
    def post(self, request):
        try:
            serializer = JobSeekerProfileSerializer(
                data=request.data,
                context={'request': request}
            )

            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Profile created",
                    "data": serializer.data
                }, status=201)

            return Response(serializer.errors, status=400)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

    # 🔹 FULL UPDATE
    def put(self, request):
        try:
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return Response({"error": "No profile found"}, status=404)

            serializer = JobSeekerProfileSerializer(
                profile,
                data=request.data,
                context={'request': request}
            )

            if serializer.is_valid():
                serializer.save()
                return Response({
                    "message": "Updated",
                    "data": serializer.data
                })

            return Response(serializer.errors, status=400)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
 
    # ── PATCH — partial update ────────────────────────────────────────────────
    def patch(self, request):
        # role_error = self._check_role(request)
        # if role_error:
        #     return role_error
 
        try:
            profile = JobSeekerProfile.objects.last()
 
            if not profile:
                return Response(
                    {'error': 'Profile not found. Please create your profile first.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
 
            serializer = JobSeekerProfileSerializer(
                profile,
                data=request.data,
                context={'request': request},
                partial=True,           # PATCH = only update sent fields
            )
 
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {'message': 'Profile updated successfully.', 'data': serializer.data},
                    status=status.HTTP_200_OK,
                )
 
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        except Exception as e:
            logger.error(f'JobSeekerProfile PATCH error for user {request.user.id}: {e}', exc_info=True)
            return Response(
                {'error': 'Something went wrong. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
