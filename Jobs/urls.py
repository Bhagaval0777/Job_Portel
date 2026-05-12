from django.urls import path

from Jobs.views import CategorySearchAPIView, CategoryCreateShowAPIView, CategoryListUpdateDeleteAPIView, JobListCreateAPIView, JobRetrieveUpdateDeleteAPIView

urlpatterns = [
    path("categories/search/",CategorySearchAPIView.as_view(),name="category-search"),
    path("categories/create/",CategoryCreateShowAPIView.as_view(),name="category-create"),
    path("categories/",CategoryListUpdateDeleteAPIView.as_view(),name="category-list-create"),
    path("create/",JobListCreateAPIView.as_view(),name="job-list-create"),
    path("update/",JobRetrieveUpdateDeleteAPIView.as_view(),name="job-detail"),
]