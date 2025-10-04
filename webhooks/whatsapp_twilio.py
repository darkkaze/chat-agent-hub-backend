from typing import Dict, Any, Optional
from sqlmodel import select
from sqlalchemy import text
from datetime import datetime, timezone
from models.channels import Chat, Message, SenderType, Channel, DeliveryStatus, ChatAgent
from models.auth import Agent
from .base import WebhookHandler
from settings import logger
from tasks.agent_tasks import process_chat_message


class WhatsAppTwilioHandler(WebhookHandler):
    """Handler for WhatsApp messages via Twilio webhook."""
    
    async def process_inbound(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process inbound WhatsApp webhook from Twilio (message or status)."""

        logger.info("Processing WhatsApp Twilio webhook", extra={
            "channel_id": channel_id,
            "data_keys": list(data.keys())
        })

        # Validate payload
        if not self.validate_payload(data):
            raise ValueError("Invalid WhatsApp Twilio payload")

        # Detect webhook type
        if self.is_status_webhook(data):
            return await self.process_status_update(data, channel_id)
        else:
            return await self.process_message(data, channel_id)

    async def process_message(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process inbound WhatsApp message."""

        # Extract message data
        message_data = self.extract_message_data(data)
        
        # Get or create chat
        chat = await self._get_or_create_chat(
            channel_id=channel_id,
            external_id=message_data["from_number"],
            contact_phone=message_data["from_number"],
            contact_name=message_data.get("profile_name", message_data["from_number"])
        )
        
        # Handle different message types
        message_content = ""
        message_type = message_data.get("message_type", "text")
        
        if message_type == "text":
            message_content = message_data["text_content"]
        elif message_type == "voice":
            # For voice messages, store media info and prepare for speech2text
            message_content = f"[Voice Message] {message_data.get('media_url', 'No URL')}"
            # TODO: Implement speech-to-text processing
            await self._process_voice_message(message_data)
        else:
            message_content = f"[{message_type.upper()} Message] {message_data.get('media_url', '')}"
        
        # Create message with enhanced Twilio metadata
        new_message = Message(
            external_id=message_data.get("message_sid"),
            chat_id=chat.id,
            content=message_content,
            sender_type=SenderType.CONTACT,
            timestamp=message_data["timestamp"],
            delivery_status=DeliveryStatus.SENT,  # Messages received via webhook are already sent
            meta_data={
                "twilio_sid": message_data.get("message_sid"),
                "from_number": message_data["from_number"],
                "to_number": message_data["to_number"],
                "profile_name": message_data.get("profile_name"),
                "message_type": message_type,
                "media_url": message_data.get("media_url"),
                "twilio_account_sid": data.get("AccountSid"),
                "twilio_messaging_service_sid": data.get("MessagingServiceSid"),
                "num_segments": data.get("NumSegments", "1"),
                "sms_status": data.get("SmsStatus"),
                "message_body_raw": data.get("Body"),
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
        """Process WhatsApp message status update."""

        message_sid = data.get("MessageSid")
        message_status = data.get("MessageStatus")

        logger.info("Processing WhatsApp status update", extra={
            "channel_id": channel_id,
            "message_sid": message_sid,
            "status": message_status
        })

        # Find the existing message by external_id (MessageSid)
        message_statement = select(Message).where(Message.external_id == message_sid)
        existing_message = self.session.exec(message_statement).first()

        if not existing_message:
            logger.warning("Message not found for status update", extra={
                "message_sid": message_sid,
                "status": message_status
            })
            return {
                "status": "warning",
                "message": f"Message {message_sid} not found for status update"
            }

        # Map Twilio status to our DeliveryStatus
        status_mapping = {
            "sent": DeliveryStatus.SENT,
            "delivered": DeliveryStatus.DELIVERED,
            "read": DeliveryStatus.READ,
            "failed": DeliveryStatus.FAILED
        }

        new_delivery_status = status_mapping.get(message_status.lower())
        if not new_delivery_status:
            logger.warning("Unknown message status", extra={
                "message_sid": message_sid,
                "status": message_status
            })
            return {
                "status": "warning",
                "message": f"Unknown status: {message_status}"
            }

        # Update the message delivery status
        existing_message.delivery_status = new_delivery_status

        # Update metadata with status update info
        existing_message.meta_data = {
            **existing_message.meta_data,
            "last_status_update": datetime.now(timezone.utc).isoformat(),
            "twilio_status_history": existing_message.meta_data.get("twilio_status_history", []) + [
                {
                    "status": message_status,
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
            "message_sid": message_sid,
            "delivery_status": new_delivery_status
        }

    def is_status_webhook(self, data: Dict[str, Any]) -> bool:
        """Check if this is a status webhook (not a message webhook)."""
        # Status webhooks have MessageStatus and MessageSid but no Body
        return "MessageStatus" in data and "MessageSid" in data and "Body" not in data

    def validate_payload(self, data: Dict[str, Any]) -> bool:
        """Validate Twilio WhatsApp webhook payload (message or status)."""

        # Check for status webhook
        if self.is_status_webhook(data):
            status_required_fields = ["MessageSid", "MessageStatus", "From", "To"]
            return all(field in data for field in status_required_fields)

        # Check for message webhook
        message_required_fields = ["From", "To", "Body"]

        # Check for basic text message fields
        has_basic_fields = all(field in data for field in message_required_fields)

        # Check for media message (voice, image, etc.)
        has_media = "MediaUrl0" in data and "MediaContentType0" in data

        # Valid if either text or media message
        return has_basic_fields or (has_media and "From" in data and "To" in data)
    
    def extract_message_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized message data from Twilio webhook."""
        
        # Basic message info
        from_number = data.get("From", "").replace("whatsapp:", "")
        to_number = data.get("To", "").replace("whatsapp:", "")
        message_sid = data.get("MessageSid", "")
        profile_name = data.get("ProfileName", "")  # Contact's WhatsApp profile name
        
        # Timestamp (Twilio doesn't always provide timestamp, use current time)
        timestamp = datetime.now(timezone.utc)
        
        # Determine message type and content
        message_type = "text"
        text_content = data.get("Body", "")
        media_url = None
        
        # Check if it's a media message
        if "MediaUrl0" in data:
            media_url = data["MediaUrl0"]
            media_type = data.get("MediaContentType0", "")
            
            if media_type.startswith("audio/"):
                message_type = "voice"
            elif media_type.startswith("image/"):
                message_type = "image"
            elif media_type.startswith("video/"):
                message_type = "video"
            else:
                message_type = "media"
        
        return {
            "from_number": from_number,
            "to_number": to_number,
            "message_sid": message_sid,
            "profile_name": profile_name,
            "timestamp": timestamp,
            "message_type": message_type,
            "text_content": text_content,
            "media_url": media_url
        }
    
    async def _get_or_create_chat(self, channel_id: str, external_id: str, contact_phone: str, contact_name: str) -> Chat:
        """Get existing chat or create new one."""
        
        # Try to find existing chat by external_id and channel
        chat_statement = select(Chat).where(
            Chat.external_id == external_id,
            Chat.channel_id == channel_id
        )
        existing_chat = self.session.exec(chat_statement).first()
        
        if existing_chat:
            return existing_chat
        
        # Create new chat with enhanced metadata
        new_chat = Chat(
            name=contact_name or f"WhatsApp {contact_phone}",
            external_id=external_id,
            channel_id=channel_id,
            last_message_ts=datetime.now(timezone.utc),
            meta_data={
                "contact_phone": contact_phone,
                "platform": "whatsapp_twilio",
                "profile_name": contact_name
            },
            extra_data={
                "twilio_integration": True,
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

        # Bulk insert ChatAgent records for all eligible agents with webhook_url
        # Set active=true only for agents with activate_for_new_conversation=true
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

        # Get all ChatAgent relationships for this chat
        chat_agent_statement = select(ChatAgent).where(ChatAgent.chat_id == message.chat_id)
        chat_agents = self.session.exec(chat_agent_statement).all()

        if not chat_agents:
            return

        # Send Celery task for each ChatAgent
        tasks_sent = []
        for chat_agent in chat_agents:
            try:
                # Send async task to Celery
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

    async def _process_voice_message(self, message_data: Dict[str, Any]) -> None:
        """Process voice message for speech-to-text conversion."""

        # TODO: Implement speech-to-text processing
        # This will be implemented later
        # For now, just log the voice message
        logger.debug("Voice message received", extra={
            "from_number": message_data.get("from_number")
        })
        pass

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
            # Don't fail the webhook if WebSocket notification fails
            logger.error("Failed to send WebSocket notification", extra={
                "chat_id": chat.id,
                "message_id": message.id,
                "error": str(e)
            })