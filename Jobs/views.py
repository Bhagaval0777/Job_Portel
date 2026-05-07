from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
# Create your views here.
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated,AllowAny
from models import Job,Category
from serializers import JobListSerializer,JobSerializer,CategorySerializer
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
        Returns paginated list of open (non-draft, non-closed) jobs.
        Supports query params:
          ?category=  ?location=  ?job_type=  ?experience_level=
          ?q=         (search in title)
          ?sort=      latest (default) | salary_high | salary_low
        """
        try:
            jobs = Job.objects.filter(status=Job.Status.OPEN).select_related(
                'company', 'category', 'recruiter__user'
            )
 
            # Search by title
            q = request.query_params.get('q', '').strip()
            if q:
                jobs = jobs.filter(title__icontains=q)
 
            # Filters
            category = request.query_params.get('category')
            if category:
                jobs = jobs.filter(category__slug=category)
 
            location = request.query_params.get('location', '').strip()
            if location:
                jobs = jobs.filter(location__icontains=location)
 
            job_type = request.query_params.get('job_type')
            if job_type:
                jobs = jobs.filter(job_type=job_type)
 
            exp_level = request.query_params.get('experience_level')
            if exp_level:
                jobs = jobs.filter(experience_level=exp_level)
 
            salary_min = request.query_params.get('salary_min')
            if salary_min:
                jobs = jobs.filter(salary_min__gte=salary_min)
 
            salary_max = request.query_params.get('salary_max')
            if salary_max:
                jobs = jobs.filter(salary_max__lte=salary_max)
 
            # Sorting
            sort = request.query_params.get('sort', 'latest')
            if sort == 'salary_high':
                jobs = jobs.order_by('-salary_max')
            elif sort == 'salary_low':
                jobs = jobs.order_by('salary_min')
            else:
                jobs = jobs.order_by('-is_featured', '-created_at')
 
            serializer = JobListSerializer(
                jobs, many=True, context={'request': request}
            )
            return Response({'count': jobs.count(), 'results': serializer.data})
 
        except Exception as e:
            logger.error(f'Job list GET error: {e}', exc_info=True)
            return Response(
                {'error': 'Something went wrong.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
 
    def post(self, request):
        """
        Recruiter creates a new job.
        recruiter and company are set automatically — never from request body.
        New jobs always start as 'draft'.
        """
        # Role check
        if getattr(request.user, 'role', None) != 'recruiter':
            return Response(
                {'error': 'Only recruiters can post jobs.'},
                status=status.HTTP_403_FORBIDDEN,
            )
 
        # Get the recruiter record linked to this user
        recruiter = get_recruiter(request.user)
        if not recruiter:
            return Response(
                {
                    'error': (
                        'You are not linked to any company. '
                        'Please complete your recruiter profile first.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
 
        try:
            serializer = JobSerializer(
                data=request.data,
                context={'request': request},
            )
            if serializer.is_valid():
                # Inject recruiter and company — not from request body
                serializer.save(
                    recruiter=recruiter,
                    company=recruiter.company,
                    status=Job.Status.DRAFT,   # always starts as draft
                )
                return Response(
                    {
                        'message': 'Job created as draft. Use PATCH /status/ to publish.',
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
                {'error': 'Something went wrong.'},
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
        Job.Status.DRAFT:  [Job.Status.OPEN],
        Job.Status.OPEN:   [Job.Status.CLOSED],
        Job.Status.CLOSED: [],   # closed is terminal — only admin can reopen
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
    Supports ?status= filter to show draft/open/closed separately.
    """
    permission_classes = [IsAuthenticated]
 
    def get(self, request):
        if getattr(request.user, 'role', None) != 'recruiter':
            return Response(
                {'error': 'Only recruiters can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN,
            )
 
        recruiter = get_recruiter(request.user)
        if not recruiter:
            return Response(
                {'error': 'Recruiter profile not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
 
        jobs = Job.objects.filter(company=recruiter.company).select_related(
            'category', 'recruiter__user'
        )
 
        # Optional status filter
        filter_status = request.query_params.get('status')
        if filter_status:
            jobs = jobs.filter(status=filter_status)
 
        serializer = JobListSerializer(jobs, many=True, context={'request': request})
        return Response({'count': jobs.count(), 'results': serializer.data})
 