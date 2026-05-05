from asyncio.log import logger
from django.shortcuts import render
from rest_framework.views import APIView
import datetime
from django.utils import timezone
from jobseeker.models import  JobSeekerProfile
from Users.serializers import UserSerializer

from asyncio.log import logger
from django.shortcuts import render
from rest_framework.views import APIView
from django.contrib.auth.models import User
# from .models import JobApplication, JobListing,
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

User = get_user_model()

class jobseekerDashboardView(APIView):
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):

        serializer = UserSerializer(request.user)
        user = User.objects.get(user_email=serializer.data['user_email'])
        profile = getattr(user, 'jobseeker_profile', None)

        if profile:
            # We define weights for completion
            # Base profile fields
            base_fields = [profile.full_name, profile.headline, profile.bio, profile.phone_number]
            
            # Check if related sets have at least one entry
            has_skills = profile.skills.exists()
            has_education = profile.educations.exists()
            has_experience = profile.experiences.exists()

            # Combine all checks into a list of booleans/values
            checks = base_fields + [has_skills, has_education, has_experience]
            
            filled_count = len([f for f in checks if f])
            total_count = len(checks)
            
            completion_rate = int((filled_count / total_count) * 100)
        else:
            logger.error(f"User {user.username} has no JobSeekerProfile.")
            completion_rate = 0

        # 2. Fetch Application Stats
        # all_apps = JobApplication.objects.filter(applicant=user).select_related('job')
        
        # Breakdown by status
        # interview_apps = all_apps.filter(status='interviewing')
        # offered_apps = all_apps.filter(status='offered')
        # rejected_apps = all_apps.filter(status='rejected')

        # Helper to format data for HTML
        # def format_apps(queryset):
        #     return [
        #         {
        #             "job_title": app.job.title,
        #             "company": app.job.company_name,
        #             "status": app.get_status_display(),
        #             "date": app.created_at.strftime("%Y-%m-%d")
        #         } for app in queryset
        #     ]

        context = {
            "profile_completion": completion_rate,
            # "counts": {
            #     "total_applied": all_apps.count(),
            #     "total_interviews": interview_apps.count(),
            #     "total_offers": offered_apps.count(),
            #     "total_rejected": rejected_apps.count(),
            # },
            # "all_applications": format_apps(all_apps.order_by('-created_at')[:5]), # Show last 5
        }
        
       
        return render(request, 'jobseeker_dashboard.html', context)

class RecruiterDashboardView(APIView):

    def get(self, request):
        user = User.objects.get(user_email='recruiter_alpha')
        profile = getattr(user, 'employer_profile', None)

        if profile:
            fields_to_check = [user.first_name, user.email, profile.company_name, profile.website, profile.description]
            filled_fields = [f for f in fields_to_check if f]
            completion_rate = int((len(filled_fields) / len(fields_to_check)) * 100)
        else:
            logger.warning(f"Employer profile missing for recruiter {user.username}")
            completion_rate = 0

        my_jobs = JobListing.objects.filter(posted_by=user).order_by('-created_at')
        
        job_postings_data = []
        for job in my_jobs:
            job_postings_data.append({
                "id": job.id,
                "title": job.title,
                "is_active": job.is_active,
                "created_at": job.created_at.strftime("%Y-%m-%d"),
                "applicant_count": job.applications.count() 
            })

        all_apps = JobApplication.objects.filter(job__in=my_jobs)
        status_summary = {
            "total_job_postings": my_jobs.count(),
            "total_applicants_received": all_apps.count(),
            "active_postings": my_jobs.filter(is_active=True).count(),
            "new_this_week": all_apps.filter(created_at__gte=timezone.now() - datetime.timedelta(days=7)).count(),
        }

        context = {
            "profile_completion": completion_rate,
            "status_summary": status_summary,
            "my_job_postings": job_postings_data,
        }

        return render(request, 'dashboard/recruiter_dashboard.html', context)