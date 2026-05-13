from django.urls import path
from .views import NotificationListView, MarkNotificationReadView, NotificationUnreadCountView

urlpatterns = [
    path('', NotificationListView.as_view(), name='notifications'),
    path('<uuid:pk>/read/', MarkNotificationReadView.as_view(), name='mark-read'),
    path('unread-count/', NotificationUnreadCountView.as_view(), name='unread-count'),
]