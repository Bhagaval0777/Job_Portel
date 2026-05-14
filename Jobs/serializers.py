from rest_framework import serializers
from django.utils import timezone
from .models import Job,Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model=Category
        fields=['category_id','name','slug','description']

class JobSerializer(serializers.ModelSerializer):
    """
        Used for:
      - Creating a new job (POST)
      - Updating a job (PUT / PATCH)
      - Reading a job with full detail (GET detail)
    """

    category_detail=CategorySerializer(source='category',read_only=True)
    company_name=serializers.CharField(source='company.name',read_only=True)
    recruiter_name=serializers.CharField(source='recruiter.user.get_full_name',read_only=True)

    class Meta:
        model  = Job
        fields = [
            # IDs and ownership (read-only)
            'id', 'recruiter', 'company', 'company_name',
            'recruiter_name',
 
            # Category
            'category', 'category_detail',
 
            # Core job details
            'title', 'description', 'location',
            'job_type', 'experience_level',
            'salary_min', 'salary_max',
            'skills_required',
            'deadline',
 
            # Status and flags
            'status',
 
            # Timestamps
            'created_at', 'updated_at',

        ]
        read_only_fields = [
            'recruiter', 'company',
            'view_count', 'created_at', 'updated_at',
        ]   

# ── Validation ────────────────────────────────────────────────────────────
 
    def validate_skills_required(self, value):
        """Skills must be a list of non-empty strings. Max 20."""
        if not isinstance(value, list):
            raise serializers.ValidationError('Skills must be a list.')
        cleaned = []
        for skill in value:
            if not isinstance(skill, str):
                raise serializers.ValidationError('Each skill must be a string.')
            skill = skill.strip()
            if skill and skill not in cleaned:
                cleaned.append(skill)
        if len(cleaned) > 20:
            raise serializers.ValidationError('Maximum 20 skills allowed.')
        return cleaned
 
    def validate_deadline(self, value):
        """Deadline must be a future date."""
        if value and value < timezone.now().date():
            raise serializers.ValidationError(
                'Deadline must be a future date.'
            )
        return value
 
    def validate(self, data):
        """Cross-field validation for salary range."""
        salary_min = data.get('salary_min')
        salary_max = data.get('salary_max')
        if salary_min and salary_max and salary_min > salary_max:
            raise serializers.ValidationError(
                {'salary_min': 'Minimum salary cannot be greater than maximum salary.'}
            )
        return data
 

class JobListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for job listing pages.
    Used in GET list — does not include full description to reduce payload size.
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    company_name  = serializers.CharField(source='company.name',  read_only=True)
    company_logo  = serializers.ImageField(source='company.logo', read_only=True)
 
    class Meta:
        model  = Job
        fields = [
            'job_id', 'title', 'company_name', 
            'location', 'job_type', 'experience_level',
            'salary_min', 'salary_max',
            'category_name', 'skills_required',
            'status', 'deadline',
            'created_at','company_logo'
        ]
 
