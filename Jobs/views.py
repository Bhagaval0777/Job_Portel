from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
# Create your views here.


from models import Job,Category
from serializers import JobListSerializer,JobSerializer,CategorySerializer

def get_recruiter(user):
    """
    Returns the Recruiter record linked to this user, or None.
    This reaches into the recruiter app — your teammate's model.
    If they named the related_name differently, adjust 'recruiter' below.
    """
    return getattr(user, 'recruiter', None)
 
def is_recruiter_for_job(user, job):
    """
    Returns True if the user is a recruiter who belongs to the
    same company that owns the job.
    """
    recruiter = get_recruiter(user)
    if not recruiter:
        return False
    return recruiter.company == job.company
 
#-----Category Views--------------------------------------------

class 