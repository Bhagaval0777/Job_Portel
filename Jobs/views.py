import logging
from asgiref.sync import sync_to_async

from django.core.cache import cache
from django.db import transaction, DatabaseError, IntegrityError

# ✅ IMPORT FROM ADRF FOR ASYNC VIEW COMPATIBILITY
from adrf.views import APIView

from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from notification.helpers import notify_user
from Jobs.models import Job, Category
from Jobs.serializers import (
    JobCreateSerializer, JobListSerializer, JobUpdateSerializer, 
    CategoryCreateSerializer, CategoryUpdateSerializer
)
from Jobs.utils import *

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
        logger.exception(f"Unhandled Exception caught by handler: {str(exc)}")
        return Response(
            {
                "success": False,
                "message": "Internal server error"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

class CategorySearchAPIView(BaseAPIView):
    pagination_class = CategoryPagination

    async def get(self, request):
        try:
            query = request.GET.get("q", "").strip().lower()
            page_number = request.GET.get("page", 1)

            logger.info(f"[CategorySearchAPIView GET] Request by user={request.user.id} | query='{query}' | page={page_number}")

            cache_key = f"category_search_{query}_{page_number}"
            cached_data = await cache.aget(cache_key)

            if cached_data:
                logger.info(f"[CategorySearchAPIView GET] Cache hit for key={cache_key}")
                return Response(cached_data)

            queryset = Category.objects.all()
            initial_count = await queryset.acount()
            logger.info(f"[CategorySearchAPIView GET] Initial category count={initial_count}")

            if query:
                queryset = queryset.filter(slug__istartswith=query)
                logger.info(f"[CategorySearchAPIView GET] Category pattern filter applied for query='{query}'")

            queryset = queryset.order_by("name")
            paginator = self.pagination_class()
            
            page = await paginate_queryset_async(paginator, queryset, request)

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

            await cache.aset(cache_key, response_data, CACHE_TIMEOUT)
            logger.info(f"[CategorySearchAPIView GET] Cache miss populated key={cache_key} | results counted={len(results)}")

            return paginator.get_paginated_response(response_data)

        except DatabaseError as db_err:
            logger.error(f"[CategorySearchAPIView GET] Database error: {str(db_err)}", exc_info=True)
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"[CategorySearchAPIView GET] Execution processing error failure: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class CategoryCreateShowAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle, HeavyRateThrottle]

    async def post(self, request):
        try:
            logger.info(f"[CategoryCreateShowAPIView POST] Attempted category creation by user={request.user.id}")
            serializer = CategoryCreateSerializer(data=request.data)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                name = serializer.validated_data["name"]
                logger.info(f"[CategoryCreateShowAPIView POST] Serializer validation pass for category name='{name}'")

                async with transaction.atomic():
                    category, created = await sync_to_async(CategoryService.get_or_create)(name=name)

                logger.info(f"[CategoryCreateShowAPIView POST] DB operation completed -> {'created new row' if created else 'matched existing row'} (ID: {category.category_id})")

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

            logger.warning(f"[CategoryCreateShowAPIView POST] Validation rejection logged: {serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError as e:
            logger.error(f"[CategoryCreateShowAPIView POST] Database integrity conflict occurred: {str(e)}", exc_info=True)
            return Response(
                {"success": False, "message": "Integrity error"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as db_err:
            logger.error(f"[CategoryCreateShowAPIView POST] Underlying database engine exception: {str(db_err)}", exc_info=True)
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"[CategoryCreateShowAPIView POST] Critical application workflow exception: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CategoryListUpdateDeleteAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle]

    async def get(self, request):
        try:
            logger.info(f"[CategoryListUpdateDeleteAPIView GET] Executing retrieval map by user={request.user.id}")
            
            data = []
            async for item in Category.objects.all().values("category_id", "name", "slug"):
                data.append(item)
            
            logger.info(f"[CategoryListUpdateDeleteAPIView GET] Active category dataset rows parsed count={len(data)}")
            return Response(
                {"success": True, "data": data},
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_err:
            logger.error(f"[CategoryListUpdateDeleteAPIView GET] Database layer communication loss: {str(db_err)}", exc_info=True)
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"[CategoryListUpdateDeleteAPIView GET] Processing stream exception hit: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def put(self, request, pk):
        try:
            logger.info(f"[CategoryListUpdateDeleteAPIView PUT] Put update requested for ID: {pk} by user={request.user.id}")
            category = await Category.objects.filter(pk=pk).afirst()

            if not category:
                logger.warning(f"[CategoryListUpdateDeleteAPIView PUT] Put routing target target mismatch for record ID: {pk}")
                return Response(
                    {"success": False, "message": "Category not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = CategoryUpdateSerializer(category, data=request.data)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                async with transaction.atomic():
                    await save_serializer(serializer)

                serialized_payload = await get_serializer_data(serializer)
                logger.info(f"[CategoryListUpdateDeleteAPIView PUT] Target entity modification successfully locked for row ID: {pk}")
                return Response(
                    {"success": True, "data": serialized_payload},
                    status=status.HTTP_200_OK
                )

            logger.warning(f"[CategoryListUpdateDeleteAPIView PUT] Parameter constraints validation failed for ID {pk}: {serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception(f"[CategoryListUpdateDeleteAPIView PUT] Runtime routine failed on ID {pk}: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def delete(self, request, pk):
        try:
            logger.warning(f"[CategoryListUpdateDeleteAPIView DELETE] Execution requested on entity primary key: {pk} by user={request.user.id}")
            category = await Category.objects.filter(pk=pk).afirst()

            if not category:
                logger.warning(f"[CategoryListUpdateDeleteAPIView DELETE] Entity processing bypassed; target record id not found: {pk}")
                return Response(
                    {"success": False, "message": "Category not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            async with transaction.atomic():
                await category.adelete()

            logger.info(f"[CategoryListUpdateDeleteAPIView DELETE] Row entry securely purged from database schema for ID: {pk}")
            return Response(
                {"success": True, "message": "Category deleted"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"[CategoryListUpdateDeleteAPIView DELETE] Structural drop runtime exception on target element {pk}: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class JobListCreateAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle, HeavyRateThrottle]

    async def get(self, request):
        try:
            logger.info(f"[JobListCreateAPIView GET] Parsing active lists for client profile identity account={request.user.id}")
            
            queryset = Job.objects.select_related("category", "recruiter").filter(
                recruiter=request.user
            ).order_by("-created_at")

            serializer = JobListSerializer(queryset, many=True)
            serialized_data = await get_serializer_data(serializer)
            
            logger.info(f"[JobListCreateAPIView GET] Parsed structural list matching user parameters. count={len(serialized_data)}")

            return Response(
                {
                    "success": True,
                    "count": len(serialized_data),
                    "data": serialized_data
                },
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_err:
            logger.error(f"[JobListCreateAPIView GET] Query expression failed at target: {str(db_err)}", exc_info=True)
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"[JobListCreateAPIView GET] Processing pipeline unexpected exception: {str(e)}")
            return Response(
                {"success": False, "message": "Unable to fetch jobs"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def post(self, request):
        try:
            logger.info(f"[JobListCreateAPIView POST] Request received to append object entry from client user={request.user.id}")
            serializer = JobCreateSerializer(data=request.data)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                validated_data = serializer.validated_data
                validated_data["recruiter"] = request.user
                async with transaction.atomic():
                    logger.info(f"[JobListCreateAPIView POST] Saving new instance metadata title='{validated_data.get('title')}'")
                    job = await Job.objects.acreate(**validated_data)

                await sync_to_async(notify_user)(
                    recipient=request.user,
                    title="Job Posted",
                    message=f"Job '{job.title}' posted successfully",
                    notification_type="system",
                    data={
                        "job_id": str(job.job_id),
                        "title_slug": job.title_slug
                    }
                )

                return_serializer = JobListSerializer(job)
                data = await get_serializer_data(return_serializer)

                logger.info(f"[JobListCreateAPIView POST] Entry row transaction verified successfully. generated ID={job.job_id}")
                return Response(
                    {
                        "success": True,
                        "message": "Job created successfully",
                        "data": data
                    },
                    status=status.HTTP_201_CREATED
                )

            logger.warning(f"[JobListCreateAPIView POST] Constraints parsing checks returned failures payload: {serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError as e:
            logger.error(f"[JobListCreateAPIView POST] Database index uniqueness/integrity rule dropped block: {str(e)}", exc_info=True)
            return Response(
                {"success": False, "message": "Integrity error"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as db_err:
            logger.error(f"[JobListCreateAPIView POST] Persistence system structural fault: {str(db_err)}", exc_info=True)
            return Response(
                {"success": False, "message": "Database error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.exception(f"[JobListCreateAPIView POST] Processing exception path drop: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class JobRetrieveUpdateDeleteAPIView(BaseAPIView):
    throttle_classes = [BurstRateThrottle, HeavyRateThrottle]
    async def get_object(self, title_slug, user):
        try:
            logger.info(f"[JobRetrieveUpdateDeleteAPIView Helper] Running filter locate pipeline for title_slug='{title_slug}' | user={user.id}")
            return await Job.objects.select_related("category", "recruiter").filter(
                title_slug=title_slug, 
                recruiter=user
            ).afirst()
        except Exception as e:
            logger.exception(f"[JobRetrieveUpdateDeleteAPIView Helper] Error mapping lookups via parameters: {str(e)}")
            return None

    async def get(self, request):
        try:
            title_slug = request.GET.get("title_slug")
            logger.info(f"[JobRetrieveUpdateDeleteAPIView GET] Read request for user={request.user.id} | title_slug='{title_slug}'")

            if title_slug:
                job = await self.get_object(title_slug, request.user)

                if not job:
                    logger.warning(f"[JobRetrieveUpdateDeleteAPIView GET] Target instance reference context empty for title_slug='{title_slug}'")
                    return Response(
                        {"success": False, "message": "Job not found or access denied"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                serializer = JobListSerializer(job)
                data = await get_serializer_data(serializer)
                logger.info(f"[JobRetrieveUpdateDeleteAPIView GET] Record trace verified for instance context job_id={job.job_id}")
                
                return Response(
                    {"success": True, "data": data},
                    status=status.HTTP_200_OK
                )

            queryset = Job.objects.select_related("category", "recruiter").filter(
                recruiter=request.user
            ).order_by("-created_at")

            serializer = JobListSerializer(queryset, many=True)
            data = await get_serializer_data(serializer)
            logger.info(f"[JobRetrieveUpdateDeleteAPIView GET] Multi-record query index returned. count={len(data)}")

            return Response(
                {
                    "success": True,
                    "count": len(data),
                    "data": data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"[JobRetrieveUpdateDeleteAPIView GET] Structural reading crash reported: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def patch(self, request):
        try:
            title_slug = request.GET.get("title_slug")
            logger.info(f"[JobRetrieveUpdateDeleteAPIView PATCH] Request received to apply delta modifications for title_slug='{title_slug}' | user={request.user.id}")
            
            job = await self.get_object(title_slug, request.user)

            if not job:
                logger.warning(f"[JobRetrieveUpdateDeleteAPIView PATCH] Cancellation token triggered; entity modification target not found.")
                return Response(
                    {"success": False, "message": "Job not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = JobUpdateSerializer(job, data=request.data, partial=True)

            is_valid = await validate_serializer(serializer)
            if is_valid:
                new_status = request.data.get("status")
                valid_statuses = [choice[0] for choice in Job.Status.choices]

                if new_status:
                    logger.info(f"[JobRetrieveUpdateDeleteAPIView PATCH] Parsing explicit state shift context parameter: new_status='{new_status}'")
                    if new_status not in valid_statuses:
                        logger.warning(f"[JobRetrieveUpdateDeleteAPIView PATCH] State validation dropped due to unrecognized enum option status='{new_status}'")
                        return Response(
                            {
                                "success": False, 
                                "message": "Invalid status",
                                "valid_statuses": valid_statuses
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )

                async with transaction.atomic():
                    await save_serializer(serializer)

                await sync_to_async(notify_user)(
                    recipient=request.user,
                    title="Job Updated",
                    message=f"Job '{job.title}' updated",
                    notification_type="system",
                    data={
                        "job_id": str(job.job_id)
                    }
                )

                data = await get_serializer_data(serializer)
                logger.info(f"[JobRetrieveUpdateDeleteAPIView PATCH] Record trace modifications merged cleanly for job_id={job.job_id}")
                return Response(
                    {
                        "success": True,
                        "message": "Job updated successfully",
                        "data": data
                    },
                    status=status.HTTP_200_OK
                )

            logger.warning(f"[JobRetrieveUpdateDeleteAPIView PATCH] Validation evaluation checks failed context payload properties: {serializer.errors}")
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception(f"[JobRetrieveUpdateDeleteAPIView PATCH] Transaction delta update routing broken: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def delete(self, request):
        try:
            title_slug = request.GET.get("title_slug")
            logger.warning(f"[JobRetrieveUpdateDeleteAPIView DELETE] Process sequence initiated for row drop: title_slug='{title_slug}' | user={request.user.id}")

            job = await self.get_object(title_slug, request.user)

            if not job:
                logger.warning(f"[JobRetrieveUpdateDeleteAPIView DELETE] Verification check returned empty; dropped drop execution mapping step safely.")
                return Response(
                    {"success": False, "message": "Job not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            async with transaction.atomic():
                await job.adelete()

            await sync_to_async(notify_user)(
                recipient=request.user,
                title="Job Deleted",
                message=f"Job '{job.title}' deleted",
                notification_type="system"
            )

            logger.info(f"[JobRetrieveUpdateDeleteAPIView DELETE] Object row entry clean drop completed from database context maps.")
            return Response(
                {"success": True, "message": "Job deleted successfully"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"[JobRetrieveUpdateDeleteAPIView DELETE] Critical database model entry reduction crash reported: {str(e)}")
            return Response(
                {"success": False, "message": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )