import logging
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.db import DatabaseError
from django.db import IntegrityError
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from Users.permissions import IsJobSeeker, IsAdminOrJobSeeker, HasResourcePermission
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import *
from .serializers import *
from .utils import custom_response

logger = logging.getLogger("jobseeker")

class BurstRateThrottle(UserRateThrottle):
    rate = "20/min"

class BaseAPIView(APIView):
    throttle_classes = [AnonRateThrottle, UserRateThrottle, BurstRateThrottle]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        logger.error(f"Unhandled Exception: {str(exc)}")
        return custom_response(False, "Internal server error", errors=str(exc), status_code=500)
    
# @login_required
def jobseeker_dashboard_view(request):
    """
    Renders the frontend HTML dashboard for the Job Seeker.
    """
    return render(request, 'profile.html')

class JobSeekerProfileView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [HasResourcePermission(), IsAuthenticated]

    def get(self, request):
        try:
            logger.info(f"Fetching profile for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                logger.warning(f"Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = JobSeekerProfileSerializer(profile)
            return custom_response(True, "Profile fetched", serializer.data)

        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    def post(self, request):
        try:
            user = request.user

            logger.info(f"Creating Profile for user {user}: {request.data}")

            if JobSeekerProfile.objects.filter(user=user).exists():
                return custom_response(
                    False,
                    "Profile already exists. Use PUT/PATCH to update.",
                    status_code=400
                )

            serializer = JobSeekerProfileSerializer(data=request.data, context={"request": request})

            if serializer.is_valid():
                serializer.save(user=user)  # attach logged-in user
                return custom_response(True, "Profile created", serializer.data)

            logger.warning(serializer.errors)
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except Exception:
            logger.exception("Error creating profile")
            return custom_response(False, "Something went wrong", status_code=500)
    
    def put(self, request):
        try:
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            serializer = JobSeekerProfileSerializer(profile, data=request.data)

            if serializer.is_valid():
                serializer.save()
                return custom_response(True, "Profile updated", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
    
    def patch(self, request):
        try:
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            serializer = JobSeekerProfileSerializer(profile, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return custom_response(True, "Profile partially updated", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

class SkillView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAdminOrJobSeeker, IsAuthenticated]

    def get(self, request, skill_id=None):
        try:
            logger.info(f"Fetching skills for user: {request.user}, Auth: {request.auth}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                logger.warning(f"Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            if skill_id:
                skill = Skill.objects.filter(
                    skill_id=skill_id,
                    profile=profile
                ).first()

                if not skill:
                    logger.warning(f"Skill not found: {skill_id}")
                    return custom_response(False, "Skill not found", status_code=404)

                serializer = SkillSerializer(skill)
                return custom_response(True, "Skill fetched", serializer.data)

            skills = Skill.objects.filter(profile=profile)
            serializer = SkillSerializer(skills, many=True)

            return custom_response(True, "Skills list", serializer.data)

        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
        
    def post(self, request):
        try:
            logger.info(f"Creating skill for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                logger.warning(f"Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)

            serializer = SkillSerializer(
                data=request.data,
                context={"request": request}
            )

            if serializer.is_valid():
                serializer.save(profile=profile)  
                logger.info("Skill created successfully")
                return custom_response(True, "Skill created", serializer.data)

            logger.warning(f"Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
    
    def delete(self, request, skill_id):
        try:
            logger.info(f"Deleting skill {skill_id} for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                logger.warning(f"Profile not found for user: {request.user}")
                return custom_response(False, "Profile not found", status_code=404)
            
            skill = Skill.objects.filter(
                skill_id=skill_id,
                profile=profile
            ).first()

            if not skill:
                logger.warning(f"Skill not found: {skill_id}")
                return custom_response(False, "Skill not found", status_code=404)

            skill.delete()
            logger.info(f"Skill deleted successfully: {skill_id}")

            return custom_response(True, "Skill deleted successfully")

        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

class PreferredLocationView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAdminOrJobSeeker, IsAuthenticated]

    def get(self, request, location_id=None):
        try:
            logger.info(f"Fetching PreferredLocation for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            if location_id:
                location = PreferredLocation.objects.filter(
                    location_id=location_id,
                    profile=profile
                ).first()

                if not location:
                    logger.warning(f"Location not found: {location_id}")
                    return custom_response(False, "Location not found", status_code=404)

                serializer = PreferredLocationSerializer(
                    location,
                    context={"request": request}
                )
                return custom_response(True, "Location fetched", serializer.data)

            locations = PreferredLocation.objects.filter(profile=profile)

            serializer = PreferredLocationSerializer(
                locations,
                many=True,
                context={"request": request}
            )

            return custom_response(True, "Locations list", serializer.data)

        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    def post(self, request):
        try:
            logger.info(f"Creating location for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            serializer = PreferredLocationSerializer(
                data=request.data,
                context={"request": request}
            )

            if serializer.is_valid():
                serializer.save(profile=profile) 
                logger.info("Location created successfully")
                return custom_response(True, "Location created", serializer.data)

            logger.warning(f"Validation failed: {serializer.errors}")
            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except IntegrityError as e:
            logger.error(f"Integrity error: {str(e)}")
            return custom_response(False, "Integrity error", status_code=400)

        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
    
    def delete(self, request, location_id):
        try:
            logger.warning(f"Deleting Location {location_id} for user: {request.user}")

            # ✅ Get logged-in user's profile
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            # ✅ Fetch only user's own location
            location = PreferredLocation.objects.filter(
                location_id=location_id,
                profile=profile
            ).first()

            if not location:
                return custom_response(False, "Location not found", status_code=404)

            location.delete()

            logger.info(f"Location deleted successfully: {location_id}")
            return custom_response(True, "Location deleted successfully")

        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

class EducationView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAdminOrJobSeeker, IsAuthenticated]

    def get(self, request, education_id=None):
        try:
            logger.info(f"Fetching Education for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            if education_id:
                education = Education.objects.filter(
                    education_id=education_id,
                    profile=profile
                ).first()

                if not education:
                    return custom_response(False, "Education not found", status_code=404)

                serializer = EducationSerializer(
                    education,
                    context={"request": request}
                )
                return custom_response(True, "Education fetched", serializer.data)

            educations = Education.objects.filter(profile=profile)

            serializer = EducationSerializer(
                educations,
                many=True,
                context={"request": request}
            )

            return custom_response(True, "Education list", serializer.data)

        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)
        
    def post(self, request):
        try:
            logger.info(f"Creating Education for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            serializer = EducationSerializer(
                data=request.data,
                context={"request": request}  
            )

            if serializer.is_valid():
                serializer.save(profile=profile)
                logger.info("Education created successfully")
                return custom_response(True, "Education created", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except IntegrityError as e:
            logger.error(f"Integrity error: {str(e)}")
            return custom_response(False, "Integrity error", status_code=400)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    def put(self, request, education_id):
        try:
            logger.info(f"Updating Education {education_id} for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            education = Education.objects.filter(
                education_id=education_id,
                profile=profile
            ).first()

            if not education:
                return custom_response(False, "Education not found", status_code=404)

            serializer = EducationSerializer(
                education,
                data=request.data,
                context={"request": request}
            )

            if serializer.is_valid():
                serializer.save()
                logger.info("Education updated successfully")
                return custom_response(True, "Education updated", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    def patch(self, request, education_id):
        try:
            logger.info(f"Partially updating Education {education_id} for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            education = Education.objects.filter(
                education_id=education_id,
                profile=profile
            ).first()

            if not education:
                return custom_response(False, "Education not found", status_code=404)

            serializer = EducationSerializer(
                education,
                data=request.data,
                partial=True,
                context={"request": request}   # 🔥 important for validation
            )

            if serializer.is_valid():
                serializer.save()
                logger.info("Education partially updated successfully")
                return custom_response(True, "Education partially updated", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

    def delete(self, request, education_id):
        try:
            logger.warning(f"Deleting Education {education_id} for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            education = Education.objects.filter(
                education_id=education_id,
                profile=profile
            ).first()

            if not education:
                return custom_response(False, "Education not found", status_code=404)

            education.delete()

            logger.info(f"Education {education_id} deleted successfully")
            return custom_response(True, "Education deleted successfully")

        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", errors=str(e), status_code=500)

class ExperienceView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]
    permission_classes = [IsAdminOrJobSeeker, IsAuthenticated]

    def get(self, request, experience_id=None):
        try:
            logger.info(f"Fetching Experience for user: {request.user}")

            # ✅ get profile from logged-in user
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            # ✅ single experience
            if experience_id:
                experience = Experience.objects.filter(
                    experience_id=experience_id,
                    profile=profile
                ).first()

                if not experience:
                    return custom_response(False, "Experience not found", status_code=404)

                serializer = ExperienceSerializer(experience)
                return custom_response(True, "Experience fetched", serializer.data)

            experiences = Experience.objects.filter(profile=profile)
            serializer = ExperienceSerializer(experiences, many=True)

            return custom_response(True, "Experience list", serializer.data)

        except DatabaseError as e:
            logger.error(str(e))
            return custom_response(False, "Database error", status_code=500)

        except Exception:
            logger.exception("Unexpected error")
            return custom_response(False, "Something went wrong", status_code=500)

    def post(self, request):
        try:
            logger.info(f"Creating Experience for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            serializer = ExperienceSerializer(
                data=request.data,
                context={"request": request}
            )

            if serializer.is_valid():
                serializer.save(profile=profile)
                return custom_response(True, "Experience created", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(str(e))
            return custom_response(False, "Database error", status_code=500)

        except Exception:
            logger.exception("Unexpected error")
            return custom_response(False, "Something went wrong", status_code=500)
        
    def put(self, request, experience_id):
        try:
            logger.info(f"Updating Experience {experience_id} for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            experience = Experience.objects.filter(
                experience_id=experience_id,
                profile=profile
            ).first()

            if not experience:
                return custom_response(False, "Experience not found", status_code=404)

            serializer = ExperienceSerializer(
                experience,
                data=request.data,
                partial=False  
            )

            if serializer.is_valid():
                serializer.save()
                logger.info("Experience updated successfully")
                return custom_response(True, "Experience updated", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(f"Database error: {str(e)}")
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)

    def patch(self, request, experience_id):
        try:
            logger.info(f"Partially updating Experience {experience_id} for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            experience = Experience.objects.filter(
                experience_id=experience_id,
                profile=profile
            ).first()

            if not experience:
                return custom_response(False, "Experience not found", status_code=404)

            serializer = ExperienceSerializer(
                experience,
                data=request.data,
                partial=True  # partial update
            )

            if serializer.is_valid():
                serializer.save()
                logger.info("Experience partially updated successfully")
                return custom_response(True, "Experience partially updated", serializer.data)

            return custom_response(False, "Validation failed", errors=serializer.errors, status_code=400)

        except DatabaseError as e:
            logger.error(str(e))
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)

    def delete(self, request, experience_id):
        try:
            logger.warning(f"Deleting Experience {experience_id} for user: {request.user}")

            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if not profile:
                return custom_response(False, "Profile not found", status_code=404)

            experience = Experience.objects.filter(
                experience_id=experience_id,
                profile=profile
            ).first()

            if not experience:
                return custom_response(False, "Experience not found", status_code=404)

            experience.delete()
            logger.info(f"Experience {experience_id} deleted successfully")

            return custom_response(True, "Experience deleted successfully")

        except DatabaseError as e:
            logger.error(str(e))
            return custom_response(False, "Database error", status_code=500)

        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return custom_response(False, "Something went wrong", status_code=500)