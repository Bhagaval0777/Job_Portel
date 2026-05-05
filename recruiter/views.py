from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Company, Recruiter
from .serializers import (
    CompanySerializer, 
    RecruiterSerializer, 
    RecruiterRegistrationSerializer
)

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

class RecruiterViewSet(viewsets.ModelViewSet):
    queryset = Recruiter.objects.all()

    def get_serializer_class(self):
        # Use the Registration serializer for POST requests
        if self.action == 'create':
            return RecruiterRegistrationSerializer
        # Use the standard serializer for everything else (GET, PUT, etc.)
        return RecruiterSerializer

    def get_permissions(self):
        # Allow anyone to register, but restrict other actions
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def me(self, request):
        try:
            recruiter = request.user.recruiter_profile
            serializer = self.get_serializer(recruiter)
            return Response(serializer.data)
        except Recruiter.DoesNotExist:
            return Response(
                {"error": "Recruiter profile not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
