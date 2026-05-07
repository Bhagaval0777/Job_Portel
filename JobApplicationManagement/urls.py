from django.urls import path
from .views import JobApplicationCreateListView, ApplicationDetailView

app_name = 'JobApplicationManagement'

urlpatterns = [
    # GET: List my applications | POST: Apply for a job
    path('apply/', JobApplicationCreateListView.as_view(), name='job-apply'),
    
    # GET: View specific application details
    path('apply/<int:application_id>/', ApplicationDetailView.as_view(), name='application-detail'),
]