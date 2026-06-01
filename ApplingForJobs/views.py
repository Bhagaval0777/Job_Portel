import logging
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from rest_framework import generics
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import render
from django.core.exceptions import ObjectDoesNotExist
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
    
class SuggestedJobsAPIView(generics.ListAPIView):
    """
    API 1: Returns jobs where AT LEAST ONE skill matches the user's profile.
    """
    serializer_class = JobListSerializer 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    # Optional: You can still order them by newest first
    ordering = ['-created_at']

    def get_queryset(self):
        # 1. Start with all open jobs
        queryset = Job.objects.filter(status='OPEN').select_related('category', 'company')
        print(queryset)
        try:
            # 2. Get the logged-in user's skills as a flat list of strings
            # This looks at the 'skill_name' field on your Skill model
            skills_queryset = self.request.user.jobseeker_profile.skills.values_list('skill_name', flat=True)
            
            # Convert the queryset to a standard Python list
            user_skills = list(skills_queryset)
            
            if user_skills and len(user_skills) > 0:
                # 3. Create an empty OR query
                skill_query = Q()
                
                # 4. If ANY single skill matches, the job will be included
                for skill in user_skills:
                    skill_query |= Q(skills_required__icontains=skill.strip())
                
                # Apply the filter and remove duplicate jobs just in case multiple skills matched
                return queryset.filter(skill_query).distinct()
                
        except (AttributeError, ObjectDoesNotExist):
            # Catch ObjectDoesNotExist just in case a user exists but hasn't created a JobSeekerProfile yet
            pass
            
        # 5. If the user has no skills or no profile, return an empty queryset
        return Job.objects.none()
    
class FilterJobsAPIView(generics.ListAPIView):
    """
    API 2: Standard search and filtering based on user inputs (Keywords, Location, etc.)
    """
    serializer_class = JobListSerializer 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    # 1. Enable standard DRF filtering tools
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # 2. EXACT match filters (e.g., dropdowns or exact strings)
    filterset_fields = ['category__name', 'company__location', 'work_type']

    # 3. KEYWORD search (e.g., typing in a search bar)
    search_fields = ['title', 'description', 'company__name']

    # 4. Sorting capabilities
    ordering_fields = ['created_at', 'salary_min', 'salary_max']
    ordering = ['-created_at'] 

    def get_queryset(self):
        # Just return all open jobs. The filter_backends will automatically 
        # slice this down based on what the user passes in the URL.
        return Job.objects.filter(status='OPEN').select_related('category', 'company')

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