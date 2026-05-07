from asyncio.log import logger
from django.shortcuts import render
from rest_framework.views import APIView
import datetime
from django.utils import timezone
from JobApplicationManagement.models import Application
from Jobs.models import Job
from Users.serializers import UserSerializer
from jobseeker.models import JobSeekerProfile

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
        user = request.user
        
        # 1. FIX: The field name is 'user', not 'job'.
        # We use .select_related to reduce database hits for related sets later.
        profile = JobSeekerProfile.objects.filter(user=user).first()

        if profile:
            # Base profile fields
            base_fields = [
                bool(profile.full_name),
                bool(profile.headline),
                bool(profile.bio),
                bool(profile.phone_number),
            ]
            
            # Related set checks
            # Note: Ensure 'skills', 'educations', etc., are defined as related_names in your models.
            has_skills = profile.skills.exists() if hasattr(profile, 'skills') else False
            has_education = profile.educations.exists() if hasattr(profile, 'educations') else False
            has_experience = profile.experiences.exists() if hasattr(profile, 'experiences') else False

            checks = base_fields + [has_skills, has_education, has_experience]
            
            filled_count = sum(1 for filled in checks if filled)
            total_count = len(checks)
            completion_rate = int((filled_count / total_count) * 100)
            
            # 2. Fetch Applications for this specific profile
# Change this:
# all_apps = Application.objects.filter(jobseeker=profile)

# To this:
            all_apps = Application.objects.filter(jobseeker=profile).select_related('job__company')        
        else:
            # Handle user with no profile gracefully
            logger.error(f"User {user.user_email} has no JobSeekerProfile.")
            completion_rate = 0
            all_apps = Application.objects.none() # Prevents errors in the rest of the view

        # 3. Stats Breakdown
        status_counts = {
            "total_applied": all_apps.count(),
            "total_interviews": all_apps.filter(status='interviewing').count(),
            "total_offers": all_apps.filter(status='offered').count(),
            "total_rejected": all_apps.filter(status='rejected').count(),
        }

        # Helper to format data for HTML
        def format_apps(queryset):
            data = []
            for app in queryset:
                data.append({
                    "job_title": app.job.title,
                    "company": app.job.company.name if app.job.company else "N/A",
                    "status": app.get_status_display(),
                    "date": app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "N/A"
                })
            return data

        context = {
            "profile_completion": completion_rate,
            "counts": status_counts,
            "all_applications": format_apps(all_apps.order_by('-applied_at')[:5]),
            "profile_missing": profile is None # Useful for showing a warning in the HTML
        }

        return render(request, 'jobseeker_dashboard.html', context)

class RecruiterDashboardView(APIView):

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        user = User.objects.get(user_email=serializer.data['user_email'])
        profile = getattr(user, 'Recruiter', None)

        if profile:
            fields_to_check = [user.first_name, user.email, profile.company.name, profile.website, profile.description]
            filled_fields = [f for f in fields_to_check if f]
            completion_rate = int((len(filled_fields) / len(fields_to_check)) * 100)
        else:
            logger.warning(f"Employer profile missing for recruiter {user.user_email}")
            completion_rate = 0

        my_jobs = Job.objects.filter(recruiter=profile).select_related('company', 'category')
        
        job_postings_data = []
        for job in my_jobs:
            job_postings_data.append({
                "id": job.id,
                "title": job.title,
                "is_active": job.status,
                "created_at": job.created_at.strftime("%Y-%m-%d"),
                "applicant_count": job.applications.count() 
            })

        all_apps = Application.objects.filter(job__in=my_jobs)
        status_summary = {
            "total_job_postings": my_jobs.count(),
            "total_applicants_received": all_apps.count(),
            "active_postings": my_jobs.filter(status='active').count(),
            "new_this_week": all_apps.filter(applied_at__gte=timezone.now() - datetime.timedelta(days=7)).count(),
        }

        context = {
            "profile_completion": completion_rate,
            "status_summary": status_summary,
            "my_job_postings": job_postings_data,
        }

        #return render(request, 'recruiter_dashboard.html', context)