from asyncio.log import logger
from django.shortcuts import render
from rest_framework.views import APIView
import datetime
from django.utils import timezone
from JobApplicationManagement.models import Application
from Jobs.models import Job
from jobseeker.models import JobSeekerProfile
from django.db.models import Count

from asyncio.log import logger
from django.shortcuts import render
from rest_framework.views import APIView
from django.contrib.auth.models import User
# from .models import JobApplication, JobListing,
from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated
from  rest_framework.permissions import AllowAny 
from Users.authentication import CustomJWTAuthentication
from rest_framework.response import Response

User = get_user_model()

class JobSeekerDashboardView(APIView):
    permission_classes = [AllowAny] 

    def get(self, request):
        # Just returns the HTML file you created earlier
        return render(request, 'jobseeker_dashboard.html')

class jobseekerDashboardDataView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # 1. FIX: The field name is 'user', not 'job'.
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
            has_skills = profile.skills.exists() if hasattr(profile, 'skills') else False
            has_education = profile.educations.exists() if hasattr(profile, 'educations') else False
            has_experience = profile.experiences.exists() if hasattr(profile, 'experiences') else False

            checks = base_fields + [has_skills, has_education, has_experience]
            
            filled_count = sum(1 for filled in checks if filled)
            total_count = len(checks)
            completion_rate = int((filled_count / total_count) * 100)
            
            # 2. Fetch Applications
            all_apps = Application.objects.filter(jobseeker=profile).select_related('job__company')      
            print(all_apps)  # Debug: Check the generated SQL query
        else:
            # Handle user with no profile gracefully
            logger.error(f"User {user.user_email} has no JobSeekerProfile.")
            completion_rate = 0
            all_apps = Application.objects.none() 

        # 3. Stats Breakdown
        status_counts = {
            "total_applied": all_apps.count(),
            "total_pending": all_apps.filter(status='Pending').count(),
            "total_accepted": all_apps.filter(status='Accepted').count(),
            "total_rejected": all_apps.filter(status='Rejected').count(),
        }

        # Helper to format data for JSON serialization
        def format_apps(queryset):
            data = []
            for app in queryset:
                data.append({
                    "application_id": app.application_id,
                    "job_title": app.job.title,
                    "category": app.job.category.name if app.job.category else "N/A",
                    "company": app.job.company.name if app.job.company else "N/A",
                    "status": app.get_status_display(),
                    # Date formatting ensures JSON compatibility
                    "date": app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "N/A"
                })
            return data

        return Response({
            "user": profile.full_name if profile else user.user_email,
            "profile_completion": completion_rate,
            "counts": status_counts,
            # FIX: Use the helper function here to serialize the queryset
            "all_applications": format_apps(all_apps.order_by('-applied_at')[:5]),
            "profile_missing": profile is None 
        })

class RecruiterDashboardDataView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'recruiter_profile', None)

        if not profile:
            return Response({"detail": "Profile missing"}, status=404)

        # 1. Profile Completion Logic
        fields_to_check = [user.user_email, profile.designation, profile.company, profile.phone_number]
        filled_fields = [f for f in fields_to_check if f]
        completion_rate = int((len(filled_fields) / len(fields_to_check)) * 100)

        # 2. Optimized Job Query
        my_jobs = Job.objects.filter(recruiter=profile).select_related('category').annotate(
            num_applicants=Count('applications')
        )
        
        # 3. Stats Summary
        all_apps = Application.objects.filter(job__in=my_jobs)
        status_summary = {
            "total_job_postings": my_jobs.count(),
            "total_applicants_received": all_apps.count(),
            "active_postings": my_jobs.filter(status='open').count(),
            "new_this_week": all_apps.filter(applied_at__gte=timezone.now() - datetime.timedelta(days=7)).count(),
        }

        # 4. CRITICAL FIX: Convert QuerySet to a LIST of DICTIONARIES
        # This converts the "Job" objects into simple JSON-friendly data
        jobs_list = []
        for job in my_jobs:
            jobs_list.append({
                "id": job.job_id,
                "title": job.title,
                "category": job.category.name if job.category else "N/A",
                "status": job.status,
                "num_applicants": job.num_applicants,
                "created_at": job.created_at.strftime("%b %d, %Y") # Date to String
            })

        # 5. Return the Response
        return Response({
            "profile_completion": completion_rate,
            "status_summary": status_summary,
            "my_job_postings": jobs_list, # Send the list, NOT the QuerySet
        })

class RecruiterDashboardView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return render(request, 'recruiter_dashboard.html')
    


class AppliedCandidatesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request, job_id):
        return render(request, 'applied_candidates.html', {"job_id": job_id})

class AppliedCandidatesDataView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        user = request.user
        profile = getattr(user, 'recruiter_profile', None)

        if not profile:
            return Response({"detail": "Profile missing"}, status=404)

        try:
            # We use job_id=job_id here because your model uses 'job_id' as the field name
            job = Job.objects.get(job_id=job_id, recruiter=profile)
        except Job.DoesNotExist:
            return Response({"detail": "Job not found or unauthorized"}, status=404)

        applications = Application.objects.filter(job=job).select_related('jobseeker__user')

        candidates_data = []
        for app in applications:
            candidates_data.append({
                "application_id": app.application_id,
                "candidate_name": app.jobseeker.full_name if app.jobseeker else "N/A",
                "candidate_email": app.jobseeker.user.user_email if app.jobseeker and app.jobseeker.user else "N/A",
                "status": app.get_status_display(),
                "applied_at": app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "N/A"
            })

        return Response({
            "job_title": job.title,
            "candidates": candidates_data
        })