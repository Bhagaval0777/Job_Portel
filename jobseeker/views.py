
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
import logging

from .models import JobSeekerProfile
from .serializers import JobSeekerProfileSerializer

logger = logging.getLogger(__name__)


def profile(request):
    return render(request, 'jobseeker/profile.html')


class JobSeekerProfileAPIView(APIView):

    # 🔹 GET PROFILE
    def get(self, request):
        try:
            profile = JobSeekerProfile.objects.first()

            if not profile:
                return Response(
                    {"message": "Profile not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = JobSeekerProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'GET error: {e}', exc_info=True)
            return Response({"error": "Something went wrong"}, status=500)

    # 🔹 CREATE PROFILE
    def post(self, request):
        '''if JobSeekerProfile.objects.exists():
                return Response(
                    {"error": "Profile already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )'''
        try:
            serializer = JobSeekerProfileSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        "message": "Profile created successfully",
                        "data": serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f'POST error: {e}', exc_info=True)
            return Response({"error": "Something went wrong"}, status=500)

    # 🔹 FULL UPDATE (PUT)
    def put(self, request):
        try:
            profile = JobSeekerProfile.objects.first()

            if not profile:
                return Response(
                    {'error': 'Profile not found. Create first.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = JobSeekerProfileSerializer(
                profile,
                data=request.data,
                partial=False
            )

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        'message': 'Profile replaced successfully',
                        'data': serializer.data
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f'PUT error: {e}', exc_info=True)
            return Response({'error': 'Something went wrong'}, status=500)

    # 🔹 PARTIAL UPDATE (PATCH)
    def patch(self, request):
        try:
            profile = JobSeekerProfile.objects.first()

            if not profile:
                return Response(
                    {'error': 'Profile not found. Create first.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            serializer = JobSeekerProfileSerializer(
                profile,
                data=request.data,
                partial=True
            )

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {
                        'message': 'Profile updated successfully',
                        'data': serializer.data
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f'PATCH error: {e}', exc_info=True)
            return Response({'error': 'Something went wrong'}, status=500)

