from rest_framework import serializers

from .models import Notification

# class NotificationSerializer(serializers.ModelSerializer):

#     class Meta:
#         model = Notification
#         fields = '__all__'

    
class NotificationListSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "message", "time"]

    def get_time(self, obj):
        from django.utils.timesince import timesince
        from django.utils import timezone
        return timesince(obj.created_at, timezone.now()) + " ago"

class NotificationSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "read_at",
            "time"
        ]

    def get_time(self, obj):
        from django.utils.timesince import timesince
        from django.utils import timezone
        return timesince(obj.created_at, timezone.now()) + " ago"
