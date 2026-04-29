from rest_framework import serializers
from .models import (
    JobSeekerProfile, Skill, PreferredLocation,
    Education, Experience
)
from .validators import phone_validator

class JobSeekerProfileSerializer(serializers.ModelSerializer):

    phone_number = serializers.CharField(
        validators=[phone_validator],
        required=True
    )

    class Meta:
        model = JobSeekerProfile
        fields = '__all__'
        read_only_fields = ['user']

    def validate(self, data):
        request = self.context.get("request")

        phone = data.get("phone_number")

        if self.instance is None:
            required_fields = ["full_name", "gender", "phone_number"]

            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                raise serializers.ValidationError(
                    f"Missing required fields: {', '.join(missing)}"
                )
            
        if phone:
            queryset = JobSeekerProfile.objects.filter(phone_number=phone)

            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise serializers.ValidationError({
                    "phone_number": "This phone number already exists"
                })

        return data

class SkillSerializer(serializers.ModelSerializer):

    class Meta:
        model = Skill
        fields = ['skill_id', 'skill_name']
        read_only_fields = ['skill_id']

    def validate_skill_name(self, value):
        request = self.context.get('request')

        if not value:
            raise serializers.ValidationError("Skill name is required")

        # ✅ normalize
        value = value.strip()

        if not request or not request.user:
            return value

        profile = JobSeekerProfile.objects.filter(user=request.user).first()

        if profile:
            if Skill.objects.filter(
                profile=profile,
                skill_name__iexact=value
            ).exists():
                raise serializers.ValidationError("Skill already exists")

        return value

class PreferredLocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = PreferredLocation
        fields = ['location_id', 'location_name'] 
        read_only_fields = ['location_id']

    def validate_location_name(self, value):
        request = self.context.get('request')

        if not value:
            raise serializers.ValidationError("Location name is required")

        value = value.strip()

        if not request or not request.user:
            return value

        profile = JobSeekerProfile.objects.filter(user=request.user).first()

        if profile:
            if PreferredLocation.objects.filter(
                profile=profile,
                location_name__iexact=value
            ).exists():
                raise serializers.ValidationError("Location already exists")

        return value

class EducationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Education
        fields = '__all__'
        read_only_fields = ['education_id', 'profile']

    def validate(self, data):
        request = self.context.get('request')

        qualification = data.get("qualification")
        start_year = data.get("start_year")
        end_year = data.get("end_year")
        is_current = data.get("is_current")

        if end_year and not is_current:
            if end_year < start_year:
                raise serializers.ValidationError({
                    "end_year": "End year cannot be before start year."
                })

        if request and request.user:
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if profile and qualification:
                queryset = Education.objects.filter(
                    profile=profile,
                    qualification__iexact=qualification.strip()
                )

                if self.instance:
                    queryset = queryset.exclude(pk=self.instance.pk)

                if  queryset.exists():
                    raise serializers.ValidationError({
                        "qualification": "This qualification already exists for your profile."
                    })

        return data

class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = '__all__'
        read_only_fields = ['experience_id', 'profile'] 

    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        is_current = data.get("is_current")

        request = self.context.get("request")

        if end_date and start_date and end_date < start_date:
            raise serializers.ValidationError({
                "end_date": "End date cannot be before start date."
            })

        if is_current:
            data["end_date"] = None

        if request and request.user:
            profile = JobSeekerProfile.objects.filter(user=request.user).first()

            if profile:
                queryset = Experience.objects.filter(
                    profile=profile,
                    company_name__iexact=data.get("company_name"),
                    role__iexact=data.get("role"),
                    start_date=data.get("start_date"),
                )

                if self.instance:
                    queryset = queryset.exclude(pk=self.instance.pk)

                if queryset.exists():
                    raise serializers.ValidationError(
                        "This experience already exists for this company, role, and start date."
                    )

        return data