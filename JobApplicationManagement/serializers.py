from rest_framework import serializers
from .models import Application

class ApplicationSerializer(serializers.ModelSerializer):
    # We display related details but keep them read-only for the POST request
    job_title = serializers.ReadOnlyField(source='job.title')
    company_name = serializers.ReadOnlyField(source='job.company.name')
    
    class Meta:
        model = Application
        fields = [
            'application_id', 'job', 'jobseeker', 'job_title', 
            'company_name', 'resume', 'cover_letter', 'status', 'applied_at'
        ]
        read_only_fields = ['status', 'applied_at', 'jobseeker']

    def validate(self, data):
        """Check if the user has already applied for this job."""
        user = self.context['request'].user
        job = data.get('job')
        
        # We check if an application already exists for this specific profile and job
        if Application.objects.filter(jobseeker__user=user, job=job).exists():
            raise serializers.ValidationError("You have already applied for this job.")
        return data