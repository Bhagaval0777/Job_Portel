from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from .models import Notification
from .serializers import NotificationSerializer  

class NotificationListView(ListAPIView):
    serializer_class = (NotificationSerializer)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = (Notification.objects.get(pk=pk, recipient=request.user))
        notification.is_read = True
        notification.read_at = (timezone.now())
        notification.save(update_fields=['is_read', 'read_at'])
        return Response({
            'success': True
        })

class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_count = (Notification.objects.filter(recipient=request.user, is_read=False).count())

        return Response({
            'unread_count': (unread_count)
            })