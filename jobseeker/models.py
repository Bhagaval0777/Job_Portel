from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from .validators import phone_validator

# Create your models here.

class JobSeekerProfile(models.Model):
    GENDER_CHOICES=(
        ('male','Male'),
        ('female','Female'),
        ('other','Other'),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="jobseeker_profile",null=True,blank=True)
    full_name=models.CharField(max_length=200)
    headline=models.CharField(max_length=255,blank=True)
    bio=models.TextField(blank=True)
    gender=models.CharField(max_length=20,choices=GENDER_CHOICES,blank=False)
    phone_number=models.CharField(max_length=15,validators=[phone_validator],blank=True)
    # profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name
    
class Skill(models.Model):
    profile=models.ForeignKey(JobSeekerProfile,on_delete=models.CASCADE,related_name="skills")
    skill_name=models.CharField(max_length=100)

    def __str__(self):
        return self.skill_name
    
class PreferredLocation(models.Model):
    profile = models.ForeignKey(JobSeekerProfile, on_delete=models.CASCADE, related_name="locations")
    location_name = models.CharField(max_length=255)

    def __str__(self):
        return self.location_name
    

class Education(models.Model):
    profile = models.ForeignKey(JobSeekerProfile, on_delete=models.CASCADE, related_name="educations")
    qualification = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255)
    institution = models.CharField(max_length=255)
    start_year = models.IntegerField()
    end_year = models.IntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.qualification} - {self.institution}"
    
    def clean(self):
        if self.end_year and not self.is_current:
            if self.end_year < self.start_year:
                raise ValidationError(
                    {'end_year': 'End year cannot be before start year.'}
                )
        if self.is_current:
            self.end_year = None 
    
class Experience(models.Model):
    EMPLOYMENT_TYPE_CHOICES = (
        ('fulltime', 'Full Time'),
        ('parttime', 'Part Time'),
        ('intern', 'Internship'),
        ('contract', 'Contract'),
    )

    profile = models.ForeignKey(JobSeekerProfile, on_delete=models.CASCADE, related_name="experiences")
    company_name = models.CharField(max_length=255)
    role = models.CharField(max_length=255)
    description = models.TextField()
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.role} at {self.company_name}"

    def clean(self):
        if self.end_date and not self.is_current:
            if self.end_date < self.start_date:
                raise ValidationError(
                    {'end_date': 'End date cannot be before start date.'}
                )
        if self.is_current:
            self.end_date = None  
