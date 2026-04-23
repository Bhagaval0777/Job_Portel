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

    def _check_role(self, request):
        """Return a 403 Response if the user is not a job seeker, else None."""
        if getattr(request.user, 'role', None) != 'jobseeker':
            return Response(
                {'error': 'Only job seekers can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None
    # 🔹 GET PROFILE
    def get(self, request):
        role_error = self._check_role(request)
        if role_error:
            return role_error
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
            # Prevent duplicate profile
            if JobSeekerProfile.objects.filter.exists():
                return Response(
                    {"error": "Profile already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = JobSeekerProfileSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                     "message": "Profile created successfully",
                     'data':serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except IntegrityError:
            return Response(
                {'error': 'Profile already exists.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        except Exception as e:
            logger.error(f'JobSeekerProfile POST error for user {request.user.id}: {e}', exc_info=True)
            return Response(
                {"error": "Something went wrong"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # 🔹 FULL UPDATE
    def put(self, request):
        role_error = self._check_role(request)
        if role_error:
            return role_error
 
        try:
            profile = JobSeekerProfile.objects.first()
 
            if not profile:
                return Response(
                    {'error': 'Profile not found. Please create your profile first.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
 
            serializer = JobSeekerProfileSerializer(
                profile,
                data=request.data,
                partial=False,          # PUT = full replacement
            )
 
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {'message': 'Profile updated successfully.', 'data': serializer.data},
                    status=status.HTTP_200_OK,
                )
 
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        except Exception as e:
            logger.error(f'JobSeekerProfile PUT error for user {request.user.id}: {e}', exc_info=True)
            return Response(
                {'error': 'Something went wrong. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
    # ── PATCH — partial update ────────────────────────────────────────────────
    def patch(self, request):
        role_error = self._check_role(request)
        if role_error:
            return role_error
 
        try:
            profile = JobSeekerProfile.objects.first()
 
            if not profile:
                return Response(
                    {'error': 'Profile not found. Please create your profile first.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
 
            serializer = JobSeekerProfileSerializer(
                profile,
                data=request.data,
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
        
