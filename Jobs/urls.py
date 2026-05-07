from django.urls import path
from . import views

urlpatterns = [
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<int:job_id>/', views.job_detail, name='job_detail'),

    # ── Categories ─────────────────────────────────────────────────────────────
    # GET  (public)  — list all categories
    # POST (admin)   — create category
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
 
    # ── Job listings ───────────────────────────────────────────────────────────
    # GET  (public)     — list all open jobs with filters
    # POST (recruiter)  — create a new job posting (starts as draft)
    path('all', views.JobListCreateView.as_view(), name='job-list-create'),
 
    # ── Recruiter's own jobs ───────────────────────────────────────────────────
    # GET (recruiter) — list all jobs for their company (?status=draft/open/closed)
    path('my-jobs/', views.RecruiterJobListView.as_view(), name='recruiter-jobs'),
    # ── Job detail ─────────────────────────────────────────────────────────────
    # GET    (public)     — view full job detail
    # PUT    (recruiter)  — full update
    # PATCH  (recruiter)  — partial update
    # DELETE (recruiter)  — delete job
    path('<int:job_id>/', views.JobDetailView.as_view(), name='job-detail'),
 
    # ── Job status control ─────────────────────────────────────────────────────
    # PATCH (recruiter) — change status: draft→open / open→closed
    path('<int:job_id>/status/', views.JobStatusView.as_view(), name='job-status'),
]