import logging
from django.shortcuts import get_object_or_404
from django.db import transaction

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import render
from rest_framework.permissions import AllowAny

# Custom Authentication
from Users.authentication import CustomJWTAuthentication

# Models
from jobseeker.models import JobSeekerProfile
from Jobs.models import Job
from JobApplicationManagement.models import Application

# Serializers
from JobApplicationManagement.serializers import ApplicationSerializer
from Jobs.serializers import JobListSerializer

logger = logging.getLogger(__name__)

class JobSearchUIView(APIView):
    """Renders the HTML page for the Job Search Interface"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return render(request, 'job_search.html')
    
class JobSearchAPIView(generics.ListAPIView):
    """
    Optimized API endpoint for Jobseekers to search and filter active jobs.
    """
    # Updated to use the correct List serializer
    serializer_class = JobListSerializer 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # EXACT match filters
    filterset_fields = ['category__name', 'company__location', 'job_type']

    # KEYWORD search
    search_fields = ['title', 'description', 'company__name']

    # SORTING
    ordering_fields = ['created_at', 'salary_min', 'salary_max']
    ordering = ['-created_at'] 

    def get_queryset(self):
        """
        Dynamically optimized queryset to prevent N+1 query problems.
        """
        # Note: If 'skills_required' is not a ManyToMany field on your Job model, 
        # you can remove the prefetch_related line safely.
        return Job.objects.filter(
            status='open'
        ).select_related(
            'category', 
            'company'
        ).prefetch_related(
            'skills' # Ensure this matches your actual ManyToMany field name, e.g., 'skills'
        )


class ApplyForJobAPIView(APIView):
    """
    Optimized endpoint to apply for a specific job with transaction safety.
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic 
    def post(self, request, job_id):
        # 1. Fetch user profile cleanly
        profile = JobSeekerProfile.objects.filter(user=request.user).first()
        
        if not profile:
            logger.warning(f"Application blocked: User {request.user.id} has no completed profile.")
            return Response(
                {"error": "You must complete your job seeker profile before applying."}, 
                status=status.HTTP_403_FORBIDDEN 
            )

        # 2. Fetch the job, ensuring it is actually open for applications
        # Ensure 'job_id' here matches your primary key field (e.g., if you named it 'job_id' in models.py)
        job = get_object_or_404(Job.objects.filter(status='open'), pk=job_id) 

        # 3. Prevent duplicate applications
        if Application.objects.filter(jobseeker=profile, job=job).exists():
            return Response(
                {"error": "You have already applied for this position."}, 
                status=status.HTTP_409_CONFLICT
            )

        # 4. Process and save
        serializer = ApplicationSerializer(data=request.data)
        
        # Automatically returns a 400 response with the errors if validation fails
        serializer.is_valid(raise_exception=True) 
        
        # Save the application with secure system-level assignments
        serializer.save(jobseeker=profile, job=job)
        
        logger.info(f"Application successful: User {request.user.user_id} applied for Job {job.pk}")
        return Response(
            {
                "success": True,
                "message": "Application submitted successfully!",
                "data": serializer.data
            }, 
            status=status.HTTP_201_CREATED
        )