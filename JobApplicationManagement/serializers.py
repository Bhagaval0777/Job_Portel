from rest_framework import serializers
from .models import Application, Job

class ApplicationSerializer(serializers.ModelSerializer):
    # Pulling details from the JobSeekerProfile via the related_name
    jobseeker_name = serializers.ReadOnlyField(source='jobseeker.jobseeker_profile.full_name')
    
    class Meta:
        model = Application
        fields = ['id', 'job', 'jobseeker', 'jobseeker_name', 'resume', 'cover_letter', 'status', 'applied_at']
        read_only_fields = ['jobseeker', 'status'] # Jobseeker is set automatically