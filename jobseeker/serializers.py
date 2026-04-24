from rest_framework import serializers
from jobseeker.models import JobSeekerProfile,Education,Experience,Skill,PreferredLocation
from .validators import validate_skill_name


class PreferredLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreferredLocation
        fields = ['id', 'location_name']
        read_only_fields = ['profile']

class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ['id', 'company_name', 'role', 'description','employment_type', 'start_date', 'end_date', 'is_current']
        read_only_fields = ['profile']

    def validate(self, data):
        start = data.get('start_date')
        end   = data.get('end_date')
        is_current = data.get('is_current', False)
        if end and not is_current and end < start:
            raise serializers.ValidationError(
                {'end_date': 'End date cannot be before start date.'}
            )
        if is_current:
            data['end_date'] = None
        return data
 
class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ['id', 'qualification', 'field_of_study','institution', 'start_year', 'end_year', 'is_current']        
        read_only_fields = ['profile']

    def validate(self, data):
        start = data.get('start_year')
        end   = data.get('end_year')
        is_current = data.get('is_current', False)
        if end and not is_current and end < start:
            raise serializers.ValidationError(
                {'end_year': 'End year cannot be before start year.'}
            )
        if is_current:
            data['end_year'] = None
        return data

class SkillSerializer(serializers.ModelSerializer):
    skill_name=serializers.CharField(validators=[validate_skill_name])
    class Meta:
        model = Skill
        fields = ['id', 'skill_name']

class JobSeekerProfileSerializer(serializers.ModelSerializer):

    skills = SkillSerializer(many=True, required=False)
    educations = EducationSerializer(many=True, required=False)
    experiences = ExperienceSerializer(many=True, required=False)
    locations = PreferredLocationSerializer(many=True, required=False)

    class Meta:
        model = JobSeekerProfile
        fields = '__all__'
        read_only_fields = ['user']

    def create(self, validated_data):
        skills_data = validated_data.pop('skills', [])
        educations_data = validated_data.pop('educations', [])
        experiences_data = validated_data.pop('experiences', [])
        locations_data = validated_data.pop('locations', [])

        # 🔥 NO USER HERE
        profile = JobSeekerProfile.objects.create(**validated_data)

        # Skills
        for skill in skills_data:
            Skill.objects.create(profile=profile, **skill)

        # Education
        for edu in educations_data:
            Education.objects.create(profile=profile, **edu)

        # Experience
        for exp in experiences_data:
            Experience.objects.create(profile=profile, **exp)

        # Locations
        for loc in locations_data:
            PreferredLocation.objects.create(profile=profile, **loc)

        return profile

    def update(self, instance, validated_data):
        skills_data = validated_data.pop('skills', [])
        educations_data = validated_data.pop('educations', [])
        experiences_data = validated_data.pop('experiences', [])
        locations_data = validated_data.pop('locations', [])

        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Replace Skills
        if skills_data is not None:
            instance.skills.all().delete()
            for skill in skills_data:
                Skill.objects.create(profile=instance, **skill)

        # Replace Education
        if educations_data is not None:
            instance.educations.all().delete()
            for edu in educations_data:
                Education.objects.create(profile=instance, **edu)

        # Replace Experience
        if experiences_data is not None:
            instance.experiences.all().delete()
            for exp in experiences_data:
                Experience.objects.create(profile=instance, **exp)

        # Replace Locations
        if locations_data is not None:
            instance.locations.all().delete()
            for loc in locations_data:
                PreferredLocation.objects.create(profile=instance, **loc)

        return instance