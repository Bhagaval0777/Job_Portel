from django.core.cache import cache
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from Jobs.models import Job, Category
from Jobs.serializers import (
    JobCreateSerializer,
    JobListSerializer,
    JobUpdateSerializer,
    CategoryCreateSerializer,
    CategoryUpdateSerializer
)

from Jobs.utils import (
    CategoryPagination,
    CategoryService,
    CACHE_TIMEOUT
)

import logging

logger = logging.getLogger("jobs")

class CategorySearchAPIView(APIView):

    permission_classes = [IsAuthenticated]
    pagination_class = CategoryPagination

    def get(self, request):

        try:

            query = request.GET.get("q", "").strip()
            page_number = request.GET.get("page", 1)

            cache_key = f"category_search_{query}_{page_number}"

            cached_data = cache.get(cache_key)

            if cached_data:

                logger.info(
                    f"Category search cache hit: {cache_key}"
                )

                return Response(cached_data)

            queryset = Category.objects.all()

            if query:
                queryset = queryset.filter(
                    slug__istartswith=query
                )

            queryset = queryset.order_by("name")

            paginator = self.pagination_class()

            page = paginator.paginate_queryset(
                queryset,
                request
            )

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

            cache.set(
                cache_key,
                response_data,
                CACHE_TIMEOUT
            )

            logger.info(
                f"Category search success: {query}"
            )

            return paginator.get_paginated_response(
                response_data
            )

        except Exception as e:

            logger.exception(
                f"Category search failed: {str(e)}"
            )

            return Response(
                {
                    "success": False,
                    "message": "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CategoryCreateShowAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        try:

            serializer = CategoryCreateSerializer(
                data=request.data
            )

            if serializer.is_valid():

                name = serializer.validated_data["name"]

                category, created = CategoryService.get_or_create(
                    name=name
                )

                logger.info(
                    f"Category create attempted"
                )

                return Response(
                    {
                        "success": True,
                        "message": (
                            "Created"
                            if created
                            else "Already exists"
                        ),
                        "data": {
                            "category_id": category.category_id,
                            "name": category.name,
                            "slug": category.slug
                        }
                    },
                    status=(
                        status.HTTP_201_CREATED
                        if created
                        else status.HTTP_200_OK
                    )
                )

            logger.warning(
                f"Category validation failed: "
                f"{serializer.errors}"
            )

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:

            logger.exception(
                f"Category create failed: {str(e)}"
            )

            return Response(
                {
                    "success": False,
                    "message": "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CategoryListUpdateDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:

            data = list(
                Category.objects.all().values(
                    "category_id",
                    "name",
                    "slug"
                )
            )

            logger.info(
                f"Category list fetched"
            )

            return Response(
                {
                    "success": True,
                    "data": data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:

            logger.exception(
                f"Category list failed: {str(e)}"
            )

            return Response(
                {
                    "success": False
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, pk):

        try:

            category = Category.objects.get(pk=pk)

            serializer = CategoryUpdateSerializer(
                category,
                data=request.data
            )

            if serializer.is_valid():

                serializer.save()

                logger.info(
                    f"Category updated: {pk}"
                )

                return Response(
                    {
                        "success": True,
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )

            logger.warning(
                f"Category update validation failed"
            )

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        except Category.DoesNotExist:

            logger.warning(
                f"Category not found: {pk}"
            )

            return Response(
                {
                    "message": "Not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:

            logger.exception(
                f"Category update failed: {str(e)}"
            )

            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):

        try:

            category = Category.objects.get(pk=pk)

            category.delete()

            logger.info(
                f"Category deleted: {pk}"
            )

            return Response(
                status=status.HTTP_204_NO_CONTENT
            )

        except Category.DoesNotExist:

            logger.warning(
                f"Category not found: {pk}"
            )

            return Response(
                {
                    "message": "Not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:

            logger.exception(
                f"Category delete failed: {str(e)}"
            )

            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class JobListCreateAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:

            queryset = Job.objects.select_related(
                "category",
                "recruiter"
            ).filter(recruiter=request.user)

            serializer = JobListSerializer(
                queryset,
                many=True
            )

            logger.info(
                f"Job list fetched"
            )

            return Response(
                {
                    "success": True,
                    "count": len(serializer.data),
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:

            logger.exception(
                f"Job list failed: {str(e)}"
            )

            return Response(
                {
                    "success": False,
                    "message": "Unable to fetch jobs"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):

        try:

            serializer = JobCreateSerializer(
                data=request.data
            )

            if serializer.is_valid():

                validated_data = serializer.validated_data

                validated_data["recruiter"] = request.user

                with transaction.atomic():

                    job = Job.objects.create(
                        **validated_data
                    )

                logger.info(
                    f"Job created: {job.job_id}"
                )

                return Response(
                    {
                        "success": True,
                        "message": "Job created successfully",
                        "data": JobListSerializer(job).data
                    },
                    status=status.HTTP_201_CREATED
                )

            logger.warning(
                f"Job create validation failed"
            )

            return Response(
                {
                    "success": False,
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:

            logger.exception(
                f"Job create failed: {str(e)}"
            )

            return Response(
                {
                    "success": False,
                    "message": "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class JobRetrieveUpdateDeleteAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get_object(self, title_slug, user):

        try:

            return Job.objects.select_related(
                "category",
                "recruiter"
            ).get(
                title_slug=title_slug,
                recruiter=user
            )

        except Job.DoesNotExist:

            logger.warning(
                f"Job not found or unauthorized: "
                f"{title_slug}"
            )

            return None

    def get(self, request):

        try:

            title_slug = request.GET.get("title_slug")

            if title_slug:

                job = self.get_object(
                    title_slug,
                    request.user
                )

                if not job:

                    return Response(
                        {
                            "success": False,
                            "message": (
                                "Job not found "
                                "or access denied"
                            )
                        },
                        status=status.HTTP_404_NOT_FOUND
                    )

                serializer = JobListSerializer(job)

                logger.info(
                    f"Single job retrieved: "
                    f"{title_slug}"
                )

                return Response(
                    {
                        "success": True,
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )
            
            queryset = Job.objects.select_related(
                "category",
                "recruiter"
            ).filter(
                recruiter=request.user
            ).order_by("-created_at")

            serializer = JobListSerializer(
                queryset,
                many=True
            )

            logger.info(
                f"All recruiter jobs fetched:"
            )

            return Response(
                {
                    "success": True,
                    "count": len(serializer.data),
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:

            logger.exception(
                f"Job retrieve failed: {str(e)}"
            )

            return Response(
                {
                    "success": False,
                    "message": "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request):

        try:
            title_slug = request.GET.get("title_slug")

            job = self.get_object(
                title_slug,
                request.user
            )

            if not job:

                return Response(
                    {
                        "success": False,
                        "message": (
                            "Job not found "
                            "or access denied"
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = JobUpdateSerializer(
                job,
                data=request.data,
                partial=True
            )

            if serializer.is_valid():

                new_status = request.data.get("status")

                valid_statuses = [
                    choice[0]
                    for choice in Job.Status.choices
                ]

                if new_status:

                    if new_status not in valid_statuses:

                        logger.warning(
                            f"Invalid status update: "
                            f"{new_status}"
                        )

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

                logger.info(
                    f"Job updated: {title_slug}"
                )

                return Response(
                    {
                        "success": True,
                        "message": (
                            "Job updated successfully"
                        ),
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK
                )

            return Response(
                {
                    "success": False,
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:

            logger.exception(
                f"Job patch failed: {str(e)}"
            )

            return Response(
                {
                    "success": False,
                    "message": "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request):

        try:
            title_slug = request.GET.get("title_slug")

            job = self.get_object(
                title_slug,
                request.user
            )

            if not job:

                return Response(
                    {
                        "success": False,
                        "message": (
                            "Job not found "
                            "or access denied"
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            with transaction.atomic():

                job.delete()

            logger.info(
                f"Job deleted: {title_slug}"
            )

            return Response(
                {
                    "success": True,
                    "message": (
                        "Job deleted successfully"
                    )
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:

            logger.exception(
                f"Job delete failed: {str(e)}"
            )

            return Response(
                {
                    "success": False,
                    "message": "Internal server error"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )