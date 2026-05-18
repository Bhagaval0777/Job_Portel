import logging
from django.core.cache import cache
from django.db import transaction, DatabaseError, IntegrityError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from Jobs.models import Job, Category
from Jobs.serializers import JobCreateSerializer, JobListSerializer, JobUpdateSerializer, CategoryCreateSerializer, CategoryUpdateSerializer
from Jobs.utils import CategoryPagination, CategoryService, CACHE_TIMEOUT

logger = logging.getLogger("jobs")

class BurstRateThrottle(UserRateThrottle):
    rate = "20/min"

class HeavyRateThrottle(UserRateThrottle):
    rate = "100/day"

class BaseAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [AnonRateThrottle, UserRateThrottle, BurstRateThrottle]

    def handle_exception(self, exc):
        logger.exception(f"Unhandled Exception: {str(exc)}")
        return Response(
            {
                "success": False,
                "message": "Internal server error"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class CategorySearchAPIView(BaseAPIView):
    pagination_class = CategoryPagination

    def get(self, request):
        try:
            query = request.GET.get("q", "").strip().lower()
            page_number = request.GET.get("page", 1)

            logger.info(f"Category search request user={request.user.id} query='{query}' page={page_number}")

            cache_key = f"category_search_{query}_{page_number}"
            cached_data = cache.get(cache_key)

            if cached_data:
                logger.info(f"Category search cache hit key={cache_key}")
                return Response(cached_data)

            queryset = Category.objects.all()
            logger.info(f"Initial category queryset count={queryset.count()}")

            if query:
                queryset = queryset.filter(slug__istartswith=query)
                logger.info(f"Category filter applied query='{query}'")

            queryset = queryset.order_by("name")
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(queryset, request)

            results = [
                {
                    "category_id": item.category_id,
                    "name": item.name,
                    "slug": item.slug
                }
                for item in page
            ]

            response_data = {
                "success": True,
                "results": results
            }

            cache.set(cache_key, response_data, CACHE_TIMEOUT)
            logger.info(f"Category search success results={len(results)}")

            return paginator.get_paginated_response(response_data)

        except DatabaseError as db_err:
            logger.error(f"Database error in category search: {str(db_err)}")
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"Category search failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class CategoryCreateShowAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle, HeavyRateThrottle]

    def post(self, request):
        try:
            logger.info(f"Category create request user={request.user.id}")
            serializer = CategoryCreateSerializer(data=request.data)

            if serializer.is_valid():
                name = serializer.validated_data["name"]
                logger.info(f"Validated category name='{name}'")

                with transaction.atomic():
                    category, created = CategoryService.get_or_create(name=name)

                logger.info(f"Category {'created' if created else 'exists'} id={category.category_id}")

                return Response(
                    {
                        "success": True,
                        "message": "Created" if created else "Already exists",
                        "data": {
                            "category_id": category.category_id,
                            "name": category.name,
                            "slug": category.slug
                        }
                    },
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
                )

            logger.warning(f"Category validation failed errors={serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError as e:
            logger.error(f"Integrity error: {str(e)}")
            return Response(
                {"success": False, "message": "Integrity error"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"Category create failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CategoryListUpdateDeleteAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]

    def get(self, request):
        try:
            logger.info(f"Fetching category list user={request.user.id}")
            data = list(Category.objects.all().values("category_id", "name", "slug"))
            
            logger.info(f"Category list fetched count={len(data)}")
            return Response(
                {"success": True, "data": data},
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"Category list failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, pk):
        try:
            logger.info(f"Category update request category_id={pk} user={request.user.id}")
            category = Category.objects.filter(pk=pk).first()

            if not category:
                logger.warning(f"Category not found id={pk}")
                return Response(
                    {"success": False, "message": "Category not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = CategoryUpdateSerializer(category, data=request.data)

            if serializer.is_valid():
                with transaction.atomic():
                    serializer.save()

                logger.info(f"Category updated id={pk}")
                return Response(
                    {"success": True, "data": serializer.data},
                    status=status.HTTP_200_OK
                )

            logger.warning(f"Category update validation failed errors={serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception(f"Category update failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        try:
            logger.warning(f"Category delete request category_id={pk} user={request.user.id}")
            category = Category.objects.filter(pk=pk).first()

            if not category:
                return Response(
                    {"success": False, "message": "Category not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with transaction.atomic():
                category.delete()

            logger.info(f"Category deleted id={pk}")
            return Response(
                {"success": True, "message": "Category deleted"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"Category delete failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class JobListCreateAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle, HeavyRateThrottle]

    def get(self, request):
        try:
            logger.info(f"Job list fetch request user={request.user.id}")
            queryset = Job.objects.select_related("category", "recruiter").filter(
                recruiter=request.user
            ).order_by("-created_at")

            serializer = JobListSerializer(queryset, many=True)
            logger.info(f"Jobs fetched successfully count={len(serializer.data)}")

            return Response(
                {
                    "success": True,
                    "count": len(serializer.data),
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"Job list failed: {str(e)}")
            return Response(
                {"success": False, "message": "Unable to fetch jobs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            logger.info(f"Job create request user={request.user.id}")
            serializer = JobCreateSerializer(data=request.data)

            if serializer.is_valid():
                validated_data = serializer.validated_data
                validated_data["recruiter"] = request.user

                with transaction.atomic():
                    logger.info(f"Creating job title='{validated_data.get('title')}'")
                    job = Job.objects.create(**validated_data)

                logger.info(f"Job created successfully job_id={job.job_id}")
                return Response(
                    {
                        "success": True,
                        "message": "Job created successfully",
                        "data": JobListSerializer(job).data
                    },
                    status=status.HTTP_201_CREATED
                )

            logger.warning(f"Job validation failed errors={serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError as e:
            logger.error(f"Integrity error: {str(e)}")
            return Response(
                {"success": False, "message": "Integrity error"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as db_err:
            logger.error(f"Database error: {str(db_err)}")
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"Job create failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class JobRetrieveUpdateDeleteAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle, HeavyRateThrottle]

    def get_object(self, title_slug, user):
        try:
            logger.info(f"Fetching job title_slug='{title_slug}' user={user.id}")
            return Job.objects.select_related("category", "recruiter").filter(
                title_slug=title_slug, 
                recruiter=user
            ).first()
        except Exception as e:
            logger.exception(f"Job fetch failed: {str(e)}")
            return None

    def get(self, request):
        try:
            title_slug = request.GET.get("title_slug")
            logger.info(f"Job retrieve request user={request.user.id} title_slug='{title_slug}'")

            if title_slug:
                job = self.get_object(title_slug, request.user)

                if not job:
                    logger.warning(f"Job not found title_slug='{title_slug}'")
                    return Response(
                        {"success": False, "message": "Job not found or access denied"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                serializer = JobListSerializer(job)
                logger.info(f"Single job fetched job_id={job.job_id}")
                
                return Response(
                    {"success": True, "data": serializer.data},
                    status=status.HTTP_200_OK
                )

            queryset = Job.objects.select_related("category", "recruiter").filter(
                recruiter=request.user
            ).order_by("-created_at")

            serializer = JobListSerializer(queryset, many=True)
            logger.info(f"All jobs fetched count={len(serializer.data)}")

            return Response(
                {
                    "success": True,
                    "count": len(serializer.data),
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"Job retrieve failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request):
        try:
            title_slug = request.GET.get("title_slug")
            logger.info(f"Job update request title_slug='{title_slug}' user={request.user.id}")
            
            job = self.get_object(title_slug, request.user)

            if not job:
                return Response(
                    {"success": False, "message": "Job not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = JobUpdateSerializer(job, data=request.data, partial=True)

            if serializer.is_valid():
                new_status = request.data.get("status")
                valid_statuses = [choice[0] for choice in Job.Status.choices]

                if new_status:
                    logger.info(f"Requested status change new_status='{new_status}'")
                    if new_status not in valid_statuses:
                        logger.warning(f"Invalid status update status='{new_status}'")
                        return Response(
                            {
                                "success": False, 
                                "message": "Invalid status",
                                "valid_statuses": valid_statuses
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )

                with transaction.atomic():
                    serializer.save()

                logger.info(f"Job updated job_id={job.job_id}")
                return Response(
                    {
                        "success": True,
                        "message": "Job updated successfully",
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )

            logger.warning(f"Job update validation failed errors={serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception(f"Job patch failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request):
        try:
            title_slug = request.GET.get("title_slug")
            logger.warning(f"Job delete request title_slug='{title_slug}' user={request.user.id}")

            job = self.get_object(title_slug, request.user)

            if not job:
                return Response(
                    {"success": False, "message": "Job not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with transaction.atomic():
                job.delete()

            logger.info(f"Job deleted job_id={job.job_id}")
            return Response(
                {"success": True, "message": "Job deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"Job delete failed: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )