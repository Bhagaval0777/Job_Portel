from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        if email and password:
            # We create users with username=email in registration, so authenticate using username
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid login credentials.")
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled.")
        else:
            raise serializers.ValidationError("Must include 'username' and 'password'.")

        data["user"] = user
        return data
 

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return value

    def validate(self, data):
        if data.get('password') != data.get('password2'):
            raise serializers.ValidationError("Passwords must match.")
        return data

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        # Use email as username to allow email-based login if desired
        user = User.objects.create_user(username=email, email=email, password=password)
        return user
    
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User # Or your CustomUser model
        fields = ['id', 'username', 'email']