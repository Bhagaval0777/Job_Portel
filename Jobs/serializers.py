from attr import attrs
from rest_framework import serializers
from .models import Job,Category

def validate_salary_range(attrs, instance=None):
    """
    Validates minimum and maximum salary boundaries for both creation 
    and partial update validation flows.
    """
    salary_min = attrs.get("salary_min")
    if salary_min is None and instance:
        salary_min = instance.salary_min

    salary_max = attrs.get("salary_max")
    if salary_max is None and instance:
        salary_max = instance.salary_max

    if salary_min is not None and salary_max is not None:
        if salary_min > salary_max:
            raise serializers.ValidationError(
                {"salary_min": "Minimum salary cannot exceed maximum salary."}
            )
    return attrs

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

    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("Category name too short")
            
        value = value.strip().title()
        
        queryset = Category.objects.filter(name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        if queryset.exists():
            raise serializers.ValidationError("A category with this name already exists.")
            
        return value

class JobCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Job
        exclude = ["created_at", "updated_at", "recruiter","title_slug"]

    def validate(self, attrs):
        return validate_salary_range(attrs, instance=self.instance)

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

    def validate(self, attrs):
        return validate_salary_range(attrs, instance=self.instance)
