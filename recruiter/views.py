# from urllib import request
from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, APIException
from rest_framework.throttling import UserRateThrottle
from django.db import IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from .serializers import CompanySerializer, RecruiterSerializer
from .models import Company, Recruiter
from .permission import HasCompanyAccess
import logging

logger = logging.getLogger(__name__)

class BurstRateThrottle(UserRateThrottle):
    """Prevents high-frequency API flooding (e.g., script attacks)."""
    scope = 'burst'
    rate = '60/minute'

class SustainedRateThrottle(UserRateThrottle):
    """Prevents continuous background scraping and resource draining."""
    scope = 'sustained'
    rate = '1000/day'

def CompanyProfileTemplate(request):
    return render(request, 'add_company.html')

def RecruiterProfileTemplate(request):
    return render(request, 'recruiter_profile.html')

class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    
    # Enforcing DDoS & brute-force protection
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def get_queryset(self):
        try:
            user = self.request.user
            recruiter = Recruiter.objects.filter(
                user=user,
                have_access=True
            ).first()

            if not recruiter:
                logger.warning(f"Access denied - Recruiter profile not found or inactive for user {getattr(user, 'user_id', 'Unknown')}")
                return Company.objects.none()

            queryset = Company.objects.filter(
                recruiters__have_access=True,
                recruiters__user=user
            ).distinct().order_by('-created_at')

            logger.info(f"Company details fetched by user {user.user_id}")
            return queryset

        except Exception as e:
            logger.error(f"Error fetching company queryset for user {self.request.user.id}: {str(e)}", exc_info=True)
            raise APIException("An unexpected error occurred while retrieving data.")

    def perform_create(self, serializer):
        try:
            user = self.request.user
            email = getattr(user, 'user_email', '').strip().lower()

            if not email or "@" not in email:
                logger.warning(f"Invalid email structure for user {user.user_id}")
                raise ValidationError("A valid email address is required to create a company.")

            domain = email.split("@")[-1].lower()
            company_name = self.request.data.get("name")

            if not company_name:
                logger.warning(f"Company name missing in request by user {user.user_id}")
                raise ValidationError("Company name is required.")

            # Validation to prevent duplicate database exceptions
            if Company.objects.filter(name__iexact=company_name).exists():
                logger.warning(f"Company name already exists: {company_name}")
                raise ValidationError("Company name already exists.")

            if Company.objects.filter(domain__iexact=domain).exists():
                logger.warning(f"Company domain already exists: {domain}")
                raise ValidationError("A company with this domain registration already exists.")

            company = serializer.save(
                created_by=user,
                domain=domain,
                is_verified=False
            )

            Recruiter.objects.create(
                user=user,
                company=company,
                is_admin=True,
                have_access=True
            )
            logger.info(f"Company and Admin recruiter successfully built by user {user.user_id}")

        except ValidationError:
            raise  # Re-raise explicit DRF validation errors
        except IntegrityError as e:
            logger.critical(f"Database Integrity violation during company creation by user {user.user_id}: {str(e)}")
            raise ValidationError("Database conflict: Ensure profile details are unique.")
        except Exception as e:
            logger.error(f"Fail-safe hit during company creation for user {user.user_id}: {str(e)}", exc_info=True)
            raise APIException("Could not complete company creation process.")

    def update(self, request, *args, **kwargs):
        try:
            company = self.get_object()
            recruiter = Recruiter.objects.filter(
                user=request.user,
                company=company,
                is_admin=True,
                have_access=True
            ).first()

            if not recruiter:
                logger.warning(f"Unauthorized update profile execution blocked for user {request.user.user_id}")
                return Response({
                    "success": False,
                    "message": "Only designated company administrators can modify details."
                }, status=status.HTTP_403_FORBIDDEN)

            partial = kwargs.pop('partial', False)
            serializer = self.get_serializer(company, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            logger.info(f"Company record updated successfully by admin {request.user.user_id}")
            return Response({
                "success": True,
                "message": "Company updated successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({"success": False, "message": "Target company file not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({"success": False, "errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Critical error updating company context via user {request.user.id}: {str(e)}", exc_info=True)
            return Response({"success": False, "message": "Internal error handling updates."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            company = self.get_object()
            recruiter = Recruiter.objects.filter(
                user=request.user,
                company=company,
                is_admin=True,
                have_access=True
            ).first()

            if not recruiter:
                logger.warning(f"Unauthorized systemic drop attempt by user {request.user.user_id}")
                return Response({
                    "success": False,
                    "message": "Only global company admins hold data destruction rights."
                }, status=status.HTTP_403_FORBIDDEN)

            company.delete()
            logger.info(f"Company instance dropped successfully by user {request.user.user_id}")
            return Response({
                "success": True,
                "message": "Company deleted successfully"
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({"success": False, "message": "Target company records could not be found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Critical purge fault encountered on user {request.user.user_id}: {str(e)}", exc_info=True)
            return Response({"success": False, "message": "System error processing data removal."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RecruiterViewSet(viewsets.ModelViewSet):
    serializer_class = RecruiterSerializer
    
    # APPLY THE PERMISSION HERE: This automatically protects retrieve, update, and destroy!
    permission_classes = [IsAuthenticated, HasCompanyAccess] 
    throttle_classes = [BurstRateThrottle, SustainedRateThrottle]

    def create(self, request, *args, **kwargs):
        user = request.user
        email = getattr(user, 'user_email', '').strip().lower()

        if not email or "@" not in email:
            logger.warning(f"Invalid email verification string for user {user.user_id}")
            return Response({"success": False, "message": "A valid institutional email is required."}, status=status.HTTP_400_BAD_REQUEST)

        domain = email.split("@")[-1]
        company = Company.objects.filter(domain__iexact=domain).first()

        if not company:
            return Response({"success": False, "message": "No registered enterprise profile found."}, status=status.HTTP_404_NOT_FOUND)

        if Recruiter.objects.filter(user=request.user).exists():
            return Response({"success": False, "message": "A recruiter profile mapping already exists."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, company=company, have_access=False, is_admin=False)

        logger.info(f"Recruiter tracking identity completed cleanly for user {request.user.user_id}")
        return Response({"success": True, "message": "Profile created", "data": serializer.data}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get', 'patch'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Allows the logged-in user to fetch or update their profile without knowing their PK"""
        recruiter = Recruiter.objects.filter(user=request.user).first()
        
        if not recruiter:
            return Response({"message": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = self.get_serializer(recruiter)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        elif request.method == 'PATCH':
            try:
                # partial=True allows us to only update the fields that are sent
                serializer = self.get_serializer(recruiter, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True) # This is where the 400 happens
                serializer.save()
                
                return Response({
                    "success": True,
                    "message": "Profile updated successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
                
            except ValidationError as e:
                # Catch the validation error and send exactly what went wrong
                return Response({
                    "success": False, 
                    "errors": e.detail
                }, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        # self.get_object() automatically applies the HasCompanyAccess permission and handles 404s
        recruiter = self.get_object()
        serializer = self.get_serializer(recruiter)
        logger.info(f"Details viewed by user {request.user.user_id}")
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        # self.get_object() handles 404 and Permission Denied automatically
        recruiter = self.get_object() 
        partial = kwargs.pop('partial', False)
        
        serializer = self.get_serializer(recruiter, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        logger.info(f"Details updated successfully by user {request.user.user_id}")
        return Response({"success": True, "message": "Recruiter updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        # self.get_object() handles 404 and Permission Denied automatically
        recruiter = self.get_object()
        recruiter.delete()
        
        logger.info(f"Recruiter tracking token deleted successfully by user {request.user.user_id}")
        return Response({"success": True, "message": "Records deleted successfully."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='give-access')
    def give_access(self, request, pk=None):
        company = self.get_object().company 
        
        # Check if requesting user is an admin for this company
        is_admin = Recruiter.objects.filter(user=request.user, company=company, is_admin=True, have_access=True).exists()
        if not is_admin:
            return Response({"success": False, "message": "Admin privileges required."}, status=status.HTTP_403_FORBIDDEN)

        user_email = request.data.get("user_email", "").strip().lower()
        recruiter = Recruiter.objects.filter(user__email=user_email, company=company).first()
        
        if not recruiter:
            return Response({"success": False, "message": "Target recruiter not found in company."}, status=status.HTTP_404_NOT_FOUND)

        recruiter.have_access = True
        recruiter.save()
        logger.info(f"Access granted safely to recruiter {recruiter.id} via operator {request.user.user_id}")
        return Response({"success": True, "message": "Access granted successfully"}, status=status.HTTP_200_OK)