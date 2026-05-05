from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
 
# Create your models here.
 
class Category(models.Model):
    '''
    Examples:Software Engineering,Design,Marketing
    '''
    category_id=models.AutoField(primary_key=True)
    name=models.CharField(max_length=100,unique=True)
    slug=models.SlugField(max_length=100,unique=True)
    description=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table="jobs_category"
        verbose_name_plural = 'Categories' # Fixes the spelling in the Admin panel (default is "Categorys")
        ordering=['name']   # Sorts categories alphabetically by name by default
 
    def __str__(self):
        return self.name
   
class Job(models.Model):
    """
    Core job posting model.
 
    Ownership chain:
        request.user → Recruiter (recruiter app) → CompanyProfile → Job
 
    Status lifecycle (recruiter controlled):
        draft → open → closed
 
    Auto-expiry:
        Celery beat task closes open jobs when deadline passes.
    """
 
    STATUS_CHOICES=(
        ('draft',"DRAFT"),
        ('open',"OPEN"),
        ('closed',"CLOSED"),
    )
 
    JOPTYPE_CHOICES=(
        ('fulltime','FULLTIME'),
        ('parttime','PARTTIME'),
        ('remote','REMOTE'),
        ('contract','CONTRACT'),
        ('internship','INTERNSHIP'),
    )
 
    EXPERIENCE_LEVEL_CHOICES=(
        ('entry','ENTRY'),
        ('mid','MID'),
        ('senior','SENIOR'),
        ('lead',"LEAD"),
    )
    recruiter = models.ForeignKey(
        'recruiter.Recruiter',
        on_delete=models.CASCADE,
        related_name='jobs',
    )
    company = models.ForeignKey(
        'recruiter.Company',
        on_delete=models.CASCADE,
        related_name='jobs',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
    )
    job_id=models.AutoField(primary_key=True)
    title=models.CharField(max_length=200)
    description=models.TextField()
    location=models.CharField(max_length=150,blank=True)
    job_type=models.CharField(max_length=20,choices=JOPTYPE_CHOICES,default="FULLTIME")
    experience_level=models.CharField(max_length=20,choices=EXPERIENCE_LEVEL_CHOICES,default="MID")
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    skills_required = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True) #Keywords or tags for better searchability (e.g., "backend, API, developer").
    deadline = models.DateField(null=True, blank=True)
    status=models.CharField(max_length=10,choices=STATUS_CHOICES,default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        db_table = 'jobs_job'
        ordering = ['-created_at']
 
    def __str__(self):
        return f'{self.title} — {self.company} [{self.status}]'
 
    def clean(self):
        if self.salary_min and self.salary_max:
            if self.salary_min > self.salary_max:
                raise ValidationError(
                    {'salary_min': 'Minimum salary cannot exceed maximum salary.'}
                )
        if self.deadline and self.status == self.Status.OPEN:
            if self.deadline < timezone.now().date():
                raise ValidationError(
                    {'deadline': 'Deadline cannot be in the past when publishing a job.'}
                )
 
    @property
    def is_open(self):
        return self.status == self.Status.OPEN
 
    @property
    def is_expired(self):
        if self.deadline:
            return self.deadline < timezone.now().date()
        return False
 