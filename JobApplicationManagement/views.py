from django.shortcuts import render
from .models import Application
from .serializers import ApplicationSerializer

# Create your views here.
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError

class ApplyJobAPIView(generics.CreateAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # 1. Ensure user is a Job Seeker
        if not self.request.user.is_jobseeker:
            raise ValidationError("Only job seekers can apply for jobs.")
        
        # 2. Prevent duplicate applications
        job_id = self.request.data.get('job')
        if Application.objects.filter(job_id=job_id, jobseeker=self.request.user).exists():
            raise ValidationError("You have already applied for this job.")
            
        # 3. Save with the current user
        serializer.save(jobseeker=self.request.user)

class JobApplicantsListAPIView(generics.ListAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        job_id = self.self.kwargs['job_id']
        # Ensure only the recruiter who owns the job can see the applicants
        return Application.objects.filter(
            job__id=job_id, 
            job__recruiter=self.request.user
        ).select_related('jobseeker__jobseeker_profile')
    
class UpdateApplicationStatusAPIView(generics.UpdateAPIView):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Security: Only allow recruiters to update applications for THEIR jobs
        return Application.objects.filter(job__recruiter=self.request.user)

    def patch(self, request, *args, **kwargs):
        # We use PATCH here because we are only updating the 'status' field
        return self.partial_update(request, *args, **kwargs)