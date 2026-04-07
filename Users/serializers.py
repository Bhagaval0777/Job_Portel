from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Users

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = Users
        fields = ["user_email", "password", "confirm_password", "role"]

    def validate(self, data):
        validate_password(data["password"])
        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")

        return Users.objects.create_user(**validated_data)