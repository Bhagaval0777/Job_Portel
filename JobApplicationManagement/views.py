from rest_framework import generics, permissions, status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from .models import Application
from .serializers import ApplicationSerializer
from jobseeker.models import JobSeekerProfile

class JobApplicationCreateListView(generics.ListCreateAPIView):
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

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

class ApplicationDetailView(generics.RetrieveAPIView):
    """
    View a specific application detail.
    """
    authentication_classes = [JWTAuthentication]
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'application_id'