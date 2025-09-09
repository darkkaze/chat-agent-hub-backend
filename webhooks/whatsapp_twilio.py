from typing import Dict, Any, Optional
from sqlmodel import select
from datetime import datetime
from models.channels import Chat, Message, SenderType, Channel
from .base import WebhookHandler
from settings import logger


class WhatsAppTwilioHandler(WebhookHandler):
    """Handler for WhatsApp messages via Twilio webhook."""
    
    async def process_inbound(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process inbound WhatsApp message from Twilio webhook."""
        
        logger.info("Processing WhatsApp Twilio webhook", extra={
            "channel_id": channel_id,
            "data_keys": list(data.keys())
        })
        
        # Validate payload
        if not self.validate_payload(data):
            raise ValueError("Invalid WhatsApp Twilio payload")
        
        # Extract message data
        message_data = self.extract_message_data(data)
        
        # Get or create chat
        chat = await self._get_or_create_chat(
            channel_id=channel_id,
            external_id=message_data["from_number"],
            contact_phone=message_data["from_number"]
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
        
        # Create message
        new_message = Message(
            external_id=message_data.get("message_sid"),
            chat_id=chat.id,
            content=message_content,
            sender_type=SenderType.CONTACT,
            timestamp=message_data["timestamp"],
            meta_data={
                "twilio_sid": message_data.get("message_sid"),
                "from_number": message_data["from_number"],
                "to_number": message_data["to_number"],
                "message_type": message_type,
                "media_url": message_data.get("media_url")
            }
        )
        
        self.session.add(new_message)
        
        # Update chat's last_message_ts
        chat.last_message_ts = message_data["timestamp"]
        self.session.add(chat)
        
        self.session.commit()
        self.session.refresh(new_message)
        self.session.refresh(chat)
        
        logger.info("WhatsApp message processed successfully", extra={
            "chat_id": chat.id,
            "message_id": new_message.id,
            "message_type": message_type
        })
        
        return {
            "status": "success",
            "chat_id": chat.id,
            "message_id": new_message.id,
            "message_type": message_type
        }
    
    def validate_payload(self, data: Dict[str, Any]) -> bool:
        """Validate Twilio WhatsApp webhook payload."""
        required_fields = ["From", "To", "Body"]
        
        # Check for basic text message fields
        has_basic_fields = all(field in data for field in required_fields)
        
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
        
        # Timestamp (Twilio doesn't always provide timestamp, use current time)
        timestamp = datetime.utcnow()
        
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
            "timestamp": timestamp,
            "message_type": message_type,
            "text_content": text_content,
            "media_url": media_url
        }
    
    async def _get_or_create_chat(self, channel_id: str, external_id: str, contact_phone: str) -> Chat:
        """Get existing chat or create new one."""
        
        # Try to find existing chat by external_id and channel
        chat_statement = select(Chat).where(
            Chat.external_id == external_id,
            Chat.channel_id == channel_id
        )
        existing_chat = self.session.exec(chat_statement).first()
        
        if existing_chat:
            return existing_chat
        
        # Create new chat
        new_chat = Chat(
            external_id=external_id,
            channel_id=channel_id,
            last_message_ts=datetime.utcnow(),
            meta_data={
                "contact_phone": contact_phone,
                "platform": "whatsapp_twilio"
            }
        )
        
        self.session.add(new_chat)
        self.session.commit()
        self.session.refresh(new_chat)
        
        return new_chat
    
    async def _process_voice_message(self, message_data: Dict[str, Any]) -> None:
        """Process voice message for speech-to-text conversion."""
        
        # TODO: Implement speech-to-text processing
        # This will be implemented later
        # For now, just log the voice message
        logger.info("Voice message received - speech2text not implemented yet", extra={
            "media_url": message_data.get("media_url"),
            "from_number": message_data.get("from_number")
        })
        pass