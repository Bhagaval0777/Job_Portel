from rest_framework import serializers
from .models import Company, Recruiter
from django.contrib.auth.models import User

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class RecruiterSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    company_details = CompanySerializer(source='company', read_only=True)

    class Meta:
        model = Recruiter
        fields = ['id', 'user', 'company', 'company_details', 'designation', 'phone_number', 'is_admin']

# --- NEW REGISTRATION SERIALIZER ---
class RecruiterRegistrationSerializer(serializers.ModelSerializer):
    # These fields belong to the User model, not the Recruiter model
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    email = serializers.EmailField(write_only=True)
    
    class Meta:
        model = Recruiter
        # We include the User fields + the Recruiter fields
        fields = ['username', 'password', 'email', 'company', 'designation', 'phone_number']

    # recruiters/serializers.py

def create(self, validated_data):
    username = validated_data.pop('username')
    password = validated_data.pop('password')
    email = validated_data.pop('email')
    
    # ADD THIS CHECK:
    if User.objects.filter(username=username).exists():
        raise serializers.ValidationError({"username": "This username is already taken."})
    
    user = User.objects.create_user(
        username=username, 
        email=email, 
        password=password
    )
    
    recruiter = Recruiter.objects.create(user=user, **validated_data)
    return recruiter
