from typing import Dict, Any, Optional
from sqlmodel import select
from sqlalchemy import text
from datetime import datetime, timezone
from models.channels import Chat, Message, SenderType, Channel, DeliveryStatus, ChatAgent
from models.auth import Agent
from .base import InboundHandler
from settings import logger
from tasks.agent_tasks import process_chat_message


class MetaWhatsAppHandler(InboundHandler):
    """Handler for WhatsApp messages via Meta official Cloud API."""

    async def process_inbound(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process inbound WhatsApp webhook from Meta Cloud API (message or status)."""

        logger.info("Processing Meta WhatsApp webhook", extra={
            "channel_id": channel_id,
            "data_keys": list(data.keys())
        })

        # Validate payload
        if not self.validate_payload(data):
            raise ValueError("Invalid Meta WhatsApp payload")

        # Detect webhook type: status update vs message
        if self.is_status_webhook(data):
            return await self.process_status_update(data, channel_id)
        else:
            return await self.process_message(data, channel_id)

    async def process_message(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process inbound WhatsApp message from Meta."""

        # Extract message data
        message_data = self.extract_message_data(data)

        # Get or create chat
        chat = await self._get_or_create_chat(
            channel_id=channel_id,
            external_id=message_data["from_number"],
            contact_phone=message_data["from_number"],
            contact_name=message_data.get("contact_name", message_data["from_number"])
        )

        # Handle different message types
        message_content = ""
        message_type = message_data.get("message_type", "text")

        if message_type == "text":
            message_content = message_data["text_content"]
        elif message_type == "image":
            message_content = f"[Image] {message_data.get('media_url', 'No URL')}"
        elif message_type == "video":
            message_content = f"[Video] {message_data.get('media_url', 'No URL')}"
        elif message_type == "audio":
            message_content = f"[Audio] {message_data.get('media_url', 'No URL')}"
        elif message_type == "document":
            message_content = f"[Document] {message_data.get('media_filename', 'Unknown')}"
        elif message_type == "location":
            message_content = f"[Location] Lat: {message_data.get('latitude')}, Lon: {message_data.get('longitude')}"
        else:
            message_content = f"[{message_type.upper()} Message]"

        # Create message with Meta metadata
        new_message = Message(
            external_id=message_data.get("message_id"),
            chat_id=chat.id,
            content=message_content,
            sender_type=SenderType.CONTACT,
            timestamp=message_data["timestamp"],
            delivery_status=DeliveryStatus.SENT,
            meta_data={
                "meta_message_id": message_data.get("message_id"),
                "from_number": message_data["from_number"],
                "contact_name": message_data.get("contact_name"),
                "message_type": message_type,
                "media_url": message_data.get("media_url"),
                "media_type": message_data.get("media_type"),
                "media_filename": message_data.get("media_filename"),
                "latitude": message_data.get("latitude"),
                "longitude": message_data.get("longitude"),
                "webhook_received_at": datetime.now(timezone.utc).isoformat()
            }
        )

        self.session.add(new_message)

        # Update chat's last_message_ts, last_sender_type, and last_message
        chat.last_message_ts = message_data["timestamp"]
        chat.last_sender_type = SenderType.CONTACT
        chat.last_message = message_content
        self.session.add(chat)

        self.session.commit()
        self.session.refresh(new_message)
        self.session.refresh(chat)

        # Process message through agents (only for CONTACT messages)
        if new_message.sender_type == SenderType.CONTACT:
            await self._process_message_with_agents(new_message, message_content)

        # Notify via WebSocket about new message
        await self._notify_websocket_new_message(chat, new_message, message_content, message_type)

        return {
            "status": "success",
            "chat_id": chat.id,
            "message_id": new_message.id,
            "message_type": message_type
        }

    async def process_status_update(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process WhatsApp message status update from Meta."""

        message_id = data.get("message_id")
        status = data.get("status")

        logger.info("Processing Meta WhatsApp status update", extra={
            "channel_id": channel_id,
            "message_id": message_id,
            "status": status
        })

        # Find the existing message by external_id
        message_statement = select(Message).where(Message.external_id == message_id)
        existing_message = self.session.exec(message_statement).first()

        if not existing_message:
            logger.warning("Message not found for status update", extra={
                "message_id": message_id,
                "status": status
            })
            return {
                "status": "warning",
                "message": f"Message {message_id} not found for status update"
            }

        # Map Meta status to our DeliveryStatus
        status_mapping = {
            "sent": DeliveryStatus.SENT,
            "delivered": DeliveryStatus.DELIVERED,
            "read": DeliveryStatus.READ,
            "failed": DeliveryStatus.FAILED
        }

        new_delivery_status = status_mapping.get(status.lower())
        if not new_delivery_status:
            logger.warning("Unknown message status", extra={
                "message_id": message_id,
                "status": status
            })
            return {
                "status": "warning",
                "message": f"Unknown status: {status}"
            }

        # Update the message delivery status
        existing_message.delivery_status = new_delivery_status

        # Update metadata with status update info
        existing_message.meta_data = {
            **existing_message.meta_data,
            "last_status_update": datetime.now(timezone.utc).isoformat(),
            "meta_status": status,
            "meta_status_history": existing_message.meta_data.get("meta_status_history", []) + [
                {
                    "status": status,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]
        }

        self.session.add(existing_message)
        self.session.commit()
        self.session.refresh(existing_message)

        logger.debug("Status updated", extra={
            "message_id": existing_message.id,
            "status": new_delivery_status
        })

        return {
            "status": "success",
            "message_id": existing_message.id,
            "external_message_id": message_id,
            "delivery_status": new_delivery_status
        }

    def is_status_webhook(self, data: Dict[str, Any]) -> bool:
        """Check if this is a status webhook (not a message webhook)."""
        return "status" in data and "message_type" not in data

    def validate_payload(self, data: Dict[str, Any]) -> bool:
        """Validate Meta WhatsApp webhook payload."""

        # Check for status webhook
        if self.is_status_webhook(data):
            status_required_fields = ["message_id", "status"]
            return all(field in data for field in status_required_fields)

        # Check for message webhook
        message_required_fields = ["message_id", "from_number", "timestamp", "message_type"]
        has_basic_fields = all(field in data for field in message_required_fields)

        if not has_basic_fields:
            return False

        # Validate message type specific fields
        message_type = data.get("message_type", "")

        if message_type == "text" and "text_content" not in data:
            return False

        if message_type in ["image", "video", "audio", "document"] and "media_url" not in data:
            return False

        if message_type == "location":
            if "latitude" not in data or "longitude" not in data:
                return False

        return True

    def extract_message_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized message data from Meta webhook."""

        message_id = data.get("message_id", "")
        from_number = data.get("from_number", "").replace("+", "")
        contact_name = data.get("contact_name", "")
        timestamp = data.get("timestamp")

        # Convert timestamp if it's a Unix timestamp
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        # Determine message type and content
        message_type = data.get("message_type", "text")
        text_content = data.get("text_content", "")
        media_url = data.get("media_url")
        media_type = data.get("media_type")
        media_filename = data.get("media_filename")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        return {
            "message_id": message_id,
            "from_number": from_number,
            "contact_name": contact_name,
            "timestamp": timestamp,
            "message_type": message_type,
            "text_content": text_content,
            "media_url": media_url,
            "media_type": media_type,
            "media_filename": media_filename,
            "latitude": latitude,
            "longitude": longitude
        }

    async def _get_or_create_chat(self, channel_id: str, external_id: str, contact_phone: str, contact_name: str) -> Chat:
        """Get existing chat or create new one."""

        chat_statement = select(Chat).where(
            Chat.external_id == external_id,
            Chat.channel_id == channel_id
        )
        existing_chat = self.session.exec(chat_statement).first()

        if existing_chat:
            return existing_chat

        # Create new chat with Meta metadata
        new_chat = Chat(
            name=contact_name or f"WhatsApp {contact_phone}",
            external_id=external_id,
            channel_id=channel_id,
            last_message_ts=datetime.now(timezone.utc),
            meta_data={
                "contact_phone": contact_phone,
                "platform": "meta_whatsapp",
                "contact_name": contact_name
            },
            extra_data={
                "meta_integration": True,
                "contact_verified": False,
                "conversation_started": datetime.now(timezone.utc).isoformat()
            }
        )

        self.session.add(new_chat)
        self.session.commit()
        self.session.refresh(new_chat)

        # Auto-assign agents to new chat
        await self._assign_agents_to_new_chat(new_chat)

        return new_chat

    async def _assign_agents_to_new_chat(self, chat: Chat) -> None:
        """Auto-assign eligible agents to new chat."""

        bulk_insert_query = text("""
            INSERT INTO chatagent (id, chat_id, agent_id, active)
            SELECT
                CONCAT('chatagent_', SUBSTRING(MD5(RANDOM()::text || CLOCK_TIMESTAMP()::text) FROM 1 FOR 10)),
                :chat_id,
                a.id,
                a.activate_for_new_conversation
            FROM agent a
            WHERE a.webhook_url IS NOT NULL AND a.is_active = true
            ON CONFLICT (chat_id, agent_id) DO NOTHING
        """)
        self.session.exec(bulk_insert_query, params={"chat_id": chat.id})
        self.session.commit()

        logger.debug("Agents auto-assigned to new chat", extra={
            "chat_id": chat.id
        })

    async def _process_message_with_agents(self, message: Message, content: str) -> None:
        """Send message to agents via Celery tasks."""

        chat_agent_statement = select(ChatAgent).where(ChatAgent.chat_id == message.chat_id)
        chat_agents = self.session.exec(chat_agent_statement).all()

        if not chat_agents:
            return

        # Send Celery task for each ChatAgent
        tasks_sent = []
        for chat_agent in chat_agents:
            try:
                task = process_chat_message.delay(
                    chat_agent_id=chat_agent.id,
                    message_id=message.id,
                    content=content
                )
                tasks_sent.append({
                    "chat_agent_id": chat_agent.id,
                    "agent_id": chat_agent.agent_id,
                    "task_id": task.id
                })

            except Exception as e:
                logger.error("Celery task failed", extra={
                    "chat_agent_id": chat_agent.id,
                    "agent_id": chat_agent.agent_id,
                    "error": str(e)
                })

        if tasks_sent:
            logger.info("Tasks sent to agents", extra={
                "chat_id": message.chat_id,
                "count": len(tasks_sent)
            })

    async def _notify_websocket_new_message(self, chat: Chat, message: Message, content: str, message_type: str) -> None:
        """Send WebSocket notification about new message."""

        try:
            from ws_service.manager import manager
            import json

            # Create preview of message content
            preview = content[:100] + "..." if len(content) > 100 else content

            # Prepare notification payload
            notification_payload = {
                "type": "new_message",
                "chat_id": chat.id,
                "channel_id": chat.channel_id,
                "message_id": message.id,
                "sender_type": message.sender_type.value,
                "timestamp": message.timestamp.isoformat(),
                "message_type": message_type,
                "preview": preview,
                "external_id": message.external_id,
                "chat_name": chat.name,
                "chat_external_id": chat.external_id
            }

            # Broadcast to all connected WebSocket clients
            await manager.broadcast(json.dumps(notification_payload))

            logger.debug("WebSocket notification sent", extra={
                "chat_id": chat.id,
                "connections": manager.get_connection_count()
            })

        except Exception as e:
            logger.error("Failed to send WebSocket notification", extra={
                "chat_id": chat.id,
                "message_id": message.id,
                "error": str(e)
            })
