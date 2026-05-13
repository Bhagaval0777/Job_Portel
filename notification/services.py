from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Notification

class NotificationService:

    @staticmethod
    def create_notification(recipient,title,message,notification_type,data=None):

        notification = (
            Notification.objects.create(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                data=data or {}
            )
        )

        channel_layer = (
            get_channel_layer()
        )

        async_to_sync(channel_layer.group_send)(
            f'user_{recipient.id}',
            {
                'type': 'send_notification',
                'data': {
                    'id': str(notification.id),
                    'title': title,
                    'message': message,
                    'notification_type': (notification_type),
                    'created_at': str(notification.created_at),
                    'is_read': False,
                }
            }
        )
        return notification