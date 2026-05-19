import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("notifications")

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        # Reject entry straight away if the incoming upgrading channel signature lacks authorization credentials
        if not self.user or self.user.is_anonymous:
            logger.warning("[WebSocket Connect] Anonymous payload rejected from opening stream pipeline.")
            await self.close(code=4030) # Forbidden Custom Code
            return

        self.user_group_name = f"user_notifications_{self.user.id}"
        logger.info(f"[WebSocket Connect] Connection opened. Binding User ID {self.user.id} to room: {self.user_group_name}")

        # Add the active websocket pipeline instance to the user's multiplex network pool
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            logger.info(f"[WebSocket Disconnect] Purging connection track link from group: {self.user_group_name} | Code: {close_code}")
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive(self, text_data):
        """Standard echo stub handler if client-side browser messages are sent."""
        pass

    async def send_notification(self, event):
        """
        Custom execution block targeting the group payload structure to 
        safely pass serial data fragments down down clean active socket pipelines.
        """
        notification_data = event["notification"]
        logger.debug(f"[WebSocket Push] Forwarding notification data array out to user endpoint. ID: {notification_data.get('notification_id')}")
        
        await self.send(text_data=json.dumps({
            "success": True,
            "data": notification_data
        }))