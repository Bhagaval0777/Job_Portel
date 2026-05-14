from django.shortcuts import render
from rest_framework import generics, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from Users.authentication import CustomJWTAuthentication
from .models import Application
from .serializers import ApplicationSerializer
from jobseeker.models import JobSeekerProfile
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny


class ApplicationListView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return render(request, 'applicationListView.html')


class JobApplicationCreateListView(generics.ListCreateAPIView):
    serializer_class = ApplicationSerializer
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return a list of all applications the current user has made.
        """
        return Application.objects.filter(jobseeker__user=self.request.user).select_related('job', 'job__company')

    def perform_create(self, serializer):
        """
        Automatically link the logged-in user's profile to the application.
        """
        profile = JobSeekerProfile.objects.get(user=self.request.user)
        serializer.save(jobseeker=profile)

class ApplicationDetailView(APIView): 
    permission_classes = [AllowAny]   
    def get(self, request, application_id): 
        return render(self.request, 'applicationDetailView.html')   

class ApplicationDetailViewData(generics.RetrieveAPIView):
    """
    View a specific application detail.
    """
    authentication_classes = [JWTAuthentication]
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'application_id'