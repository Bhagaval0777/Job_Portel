from rest_framework import serializers
from django.utils import timezone
from .models import Job,Category

class CategoryCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ["name"]

    def validate_name(self, value):

        if len(value.strip()) < 3:
            raise serializers.ValidationError("Category name too short")
        
        value = value.strip().title()

        if Category.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Category already exists")

        return value

class CategoryListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = [
            "category_id",
            "name",
            "slug",
            "created_at"
        ]

class CategoryUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ["name"]

class JobCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Job
        exclude = ["created_at", "updated_at", "recruiter","title_slug"]

    def validate(self, attrs):

        salary_min = attrs.get("salary_min")
        salary_max = attrs.get("salary_max")

        if salary_min and salary_max:
            if salary_min > salary_max:
                raise serializers.ValidationError(
                    "Minimum salary cannot exceed maximum salary"
                )

        return attrs

class JobListSerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )

    class Meta:
        model = Job
        fields = "__all__"

class JobUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Job
        exclude = ["created_at", "updated_at"]
