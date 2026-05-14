from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated,AllowAny
from Jobs.models import Job, Category
from .serializers import JobListSerializer,JobSerializer,CategorySerializer
import logging
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

def get_recruiter(user):
    """
    Returns the Recruiter record linked to this user, or None.
    This reaches into the recruiter app — your teammate's model.
    If they named the related_name differently, adjust 'recruiter' below.
    """
    return getattr(user, 'recruiter', None)
 
def is_recruiter_for_job(user, job):
    """
    Returns True if the user is a recruiter who belongs to the
    same company that owns the job.
    """
    recruiter = get_recruiter(user)
    if not recruiter:
        return False
    return recruiter.company == job.company
 
#-----Category Views--------------------------------------------

class CategoryListView(APIView):
    """
    GET /api/v1/jobs/categories/
    Public — anyone can list categories.
    POST /api/v1/jobs/categories/  — admin and recruitor only (create new category)
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get(self,request):
        categories=Category.objects.all()
        serializer_instance=CategorySerializer(categories,many=True)
        return Response(serializer_instance.data)
    
    def post(self,request):
        serializer_instance=CategorySerializer(data=request.data)
        if serializer_instance.is_valid():
            serializer_instance.save()
            return Response(serializer_instance.data,status=status.HTTP_201_CREATED)
        return Response(serializer_instance.errors,status=status.HTTP_400_BAD_REQUEST)
    
#-----Job List + Create----------------

class JobListCreateView(APIView):
    """
    GET  /api/v1/jobs/           — public list of all open jobs
    POST /api/v1/jobs/           — recruiter creates a new job (draft by default)
    """
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        """
        Returns paginated list of open jobs with filtering and search.
        """
        try:
            # 1. Base Queryset (Using string 'open' to avoid AttributeError)
            jobs = Job.objects.filter(status='open').select_related(
                'company', 'category', 'recruiter__user'
            )

            # 2. Search by title
            q = request.query_params.get('q', '').strip()
            if q:
                jobs = jobs.filter(title__icontains=q)

            # 3. Category & Location Filters
            category = request.query_params.get('category')
            if category:
                jobs = jobs.filter(category__slug=category)

            location = request.query_params.get('location', '').strip()
            if location:
                jobs = jobs.filter(location__icontains=location)

            # 4. Dropdown Filters (Job Type / Exp Level)
            job_type = request.query_params.get('job_type')
            if job_type:
                jobs = jobs.filter(job_type=job_type)

            exp_level = request.query_params.get('experience_level')
            if exp_level:
                jobs = jobs.filter(experience_level=exp_level)

            # 5. Salary Range Filters (With basic numeric validation)
            salary_min = request.query_params.get('salary_min')
            if salary_min and salary_min.isdigit():
                jobs = jobs.filter(salary_min__gte=salary_min)

            salary_max = request.query_params.get('salary_max')
            if salary_max and salary_max.isdigit():
                jobs = jobs.filter(salary_max__lte=salary_max)

            # 6. Sorting (Removed 'is_featured' to prevent FieldError)
            sort = request.query_params.get('sort', 'latest')
            if sort == 'salary_high':
                jobs = jobs.order_by('-salary_max')
            elif sort == 'salary_low':
                jobs = jobs.order_by('salary_min')
            else:
                jobs = jobs.order_by('-created_at')

            # 7. Serialization
            serializer = JobListSerializer(
                jobs, many=True, context={'request': request}
            )
            
            return Response({
                'count': jobs.count(), 
                'results': serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'Job list GET error: {e}', exc_info=True)
            return Response(
                {'error': 'An internal error occurred while fetching jobs.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """
        Recruiter creates a new job. 
        Note: recruiter and company are handled by the view, not the request body.
        """
        # Role check (Assuming 'role' is a field on your custom User model)
        if getattr(request.user, 'role', None) != 'recruiter':
            return Response(
                {'error': 'Access denied. Only recruiters can post jobs.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get the recruiter record linked to this user
        # Note: Ensure get_recruiter helper is defined/imported
        try:
            # This is a placeholder for your specific logic to get the recruiter profile
            from .models import Recruiter
            recruiter = Recruiter.objects.get(user=request.user)
        except Exception:
            return Response(
                {'error': 'Recruiter profile not found. Please complete your profile.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            serializer = JobSerializer(
                data=request.data,
                context={'request': request},
            )
            
            if serializer.is_valid():
                # Injecting data: Using string 'draft' instead of Job.Status.DRAFT
                serializer.save(
                    recruiter=recruiter,
                    company=recruiter.company,
                    status='draft' 
                )
                
                return Response(
                    {
                        'message': 'Job created as draft successfully.',
                        'data': serializer.data,
                    },
                    status=status.HTTP_201_CREATED,
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(
                f'Job POST error for user {request.user.id}: {e}', exc_info=True
            )
            return Response(
                {'error': 'Failed to create job.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
# ─── Job Detail + Update + Delete ────────────────────────────────────────────
 
class JobDetailView(APIView):
    """
    GET    /api/v1/jobs/{id}/   — public, increments view_count
    PUT    /api/v1/jobs/{id}/   — full update (recruiter, own company only)
    PATCH  /api/v1/jobs/{id}/   — partial update
    DELETE /api/v1/jobs/{id}/   — delete (recruiter owner or admin)
    """
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
 
    def get(self, request, job_id):
        job = get_object_or_404(
            Job.objects.select_related('company', 'category', 'recruiter__user'),
            pk=job_id,
        )
 
        # Non-open jobs visible to recruiter of that company and admins only
        if job.status != Job.Status.OPEN:
            if not request.user.is_authenticated:
                return Response(
                    {'error': 'This job is not currently available.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not (request.user.is_superuser or is_recruiter_for_job(request.user, job)):
                return Response(
                    {'error': 'This job is not currently available.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
 
        # Atomic view count increment
        job.increment_view_count()
 
        serializer = JobSerializer(job, context={'request': request})
        return Response(serializer.data)
 
    def put(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
        return self._update(request, job, partial=False)
 
    def patch(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
        return self._update(request, job, partial=True)
 
    def _update(self, request, job, partial):
        # Admin can update anything
        # Recruiter can only update jobs belonging to their company
        if not request.user.is_superuser:
            if not is_recruiter_for_job(request.user, job):
                return Response(
                    {'error': 'You can only edit jobs from your own company.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
 
        try:
            serializer = JobSerializer(
                job,
                data=request.data,
                context={'request': request},
                partial=partial,
            )
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {'message': 'Job updated successfully.', 'data': serializer.data}
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 
        except Exception as e:
            logger.error(f'Job update error {job.id}: {e}', exc_info=True)
            return Response(
                {'error': 'Something went wrong.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
    def delete(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
 
        # Permission check
        if not request.user.is_superuser:
            if not is_recruiter_for_job(request.user, job):
                return Response(
                    {'error': 'You can only delete jobs from your own company.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
 
        try:
            job_title = job.title
            job.delete()
            return Response(
                {'message': f'Job "{job_title}" deleted successfully.'},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f'Job delete error {job_id}: {e}', exc_info=True)
            return Response(
                {'error': 'Something went wrong.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
 
# ─── Job Status Control ───────────────────────────────────────────────────────
 
class JobStatusView(APIView):
    """
    PATCH /api/v1/jobs/{id}/status/
    Controls the job status lifecycle: draft → open → closed
 
    Body: { "status": "open" }   or   { "status": "closed" }
    """
    permission_classes = [IsAuthenticated]
 
    # Valid transitions — prevents jumping from closed back to draft etc.
    VALID_TRANSITIONS = {
        'draft':  ['open'],
        'open':   ['closed'],
        'closed': [],   # terminal state
        }
 
    def patch(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
 
        # Permission check
        if not request.user.is_superuser:
            if not is_recruiter_for_job(request.user, job):
                return Response(
                    {'error': 'You can only manage jobs from your own company.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
 
        new_status = request.data.get('status', '').strip()
 
        if not new_status:
            return Response(
                {'error': 'status field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        valid_choices = [c[0] for c in Job.Status.choices]
        if new_status not in valid_choices:
            return Response(
                {'error': f'Invalid status. Choose from: {valid_choices}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # Admins can set any status; recruiters follow transition rules
        if not request.user.is_superuser:
            allowed = self.VALID_TRANSITIONS.get(job.status, [])
            if new_status not in allowed:
                return Response(
                    {
                        'error': (
                            f'Cannot change status from "{job.status}" to "{new_status}". '
                            f'Allowed transitions: {allowed or "none"}'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
 
        job.status = new_status
        job.save(update_fields=['status', 'updated_at'])
 
        return Response(
            {
                'message': f'Job status updated to "{new_status}".',
                'job_id': job.id,
                'status': job.status,
            }
        )
 
 
# ─── Recruiter's Own Job Listings ────────────────────────────────────────────
 
class RecruiterJobListView(APIView):
    """
    GET /api/v1/jobs/my-jobs/
    Returns all jobs posted by the authenticated recruiter's company.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # 1. Role Check
        if getattr(request.user, 'role', None) != 'recruiter':
            return Response(
                {'error': 'Only recruiters can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Get Recruiter Profile
        # Note: Using your helper function get_recruiter
        recruiter = get_recruiter(request.user)
        if not recruiter or not recruiter.company:
            return Response(
                {'error': 'Recruiter profile or associated company not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 3. Fetch Jobs
        # Optimization: added 'company' to select_related for the JobListSerializer logo
        jobs = Job.objects.filter(company=recruiter.company).select_related(
            'company', 'category', 'recruiter__user'
        ).order_by('-created_at')

        # 4. Optional status filter (e.g., ?status=draft)
        filter_status = request.query_params.get('status')
        if filter_status:
            # We use lowercase because your STATUS_CHOICES keys are likely 'draft', 'open', etc.
            jobs = jobs.filter(status=filter_status.lower())

        # 5. Serialization
        # Passing context={'request': request} is CRITICAL for absolute image URLs (logos)
        serializer = JobListSerializer(jobs, many=True, context={'request': request})
        
        return Response({
            'count': jobs.count(), 
            'results': serializer.data
        }, status=status.HTTP_200_OK)