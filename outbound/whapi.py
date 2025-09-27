import httpx
import asyncio
import random
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from sqlmodel import Session, select
from models.channels import Chat, Message, Channel, SenderType
from .base import OutboundHandler
from settings import logger


class WhapiOutboundHandler(OutboundHandler):
    """Handler for sending WhatsApp messages via WHAPI API."""

    async def send_message(self, chat: Chat, message: Message, channel: Channel) -> Dict[str, Any]:
        """Send message to WhatsApp via WHAPI API."""

        logger.info("Sending WhatsApp message via WHAPI", extra={
            "chat_id": chat.id,
            "message_id": message.id,
            "channel_id": channel.id
        })

        # Validate channel configuration
        if not self.validate_channel_config(channel):
            raise ValueError("Invalid WHAPI channel configuration")

        # Check if we need to add delay for new conversations
        should_delay = await self._should_apply_conversation_delay(chat)
        if should_delay:
            delay_seconds = self._get_conversation_delay()
            logger.info("Adding intelligent conversation delay", extra={
                "chat_id": chat.id,
                "delay_seconds": delay_seconds
            })
            await asyncio.sleep(delay_seconds)

        # Calculate typing time based on message length
        typing_time = self._calculate_typing_time(message.content)

        # Extract credentials
        credentials = channel.credentials_to_send_message
        token = credentials.get("token")

        # Extract phone number from chat
        to_number = self._extract_phone_number(chat)

        if not to_number:
            raise ValueError("No recipient phone number found in chat")

        # Prepare API request
        url = "https://gate.whapi.cloud/messages/text"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Prepare request body
        request_body = {
            "to": to_number,
            "body": message.content,
            "typing_time": typing_time
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=30.0
                )

                response.raise_for_status()
                response_data = response.json()

                logger.info("WHAPI message sent successfully", extra={
                    "message_id": message.id,
                    "chat_id": chat.id,
                    "whapi_message_id": response_data.get("id"),
                    "typing_time": typing_time
                })

                return {
                    "status": "sent",
                    "external_id": response_data.get("id"),
                    "platform_response": response_data,
                    "typing_time": typing_time,
                    "to_number": to_number
                }

        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP {e.response.status_code}"
            try:
                error_response = e.response.json()
                error_detail = error_response.get("message", error_detail)
            except:
                pass

            logger.error("Failed to send WHAPI message", extra={
                "message_id": message.id,
                "chat_id": chat.id,
                "error": error_detail,
                "status_code": e.response.status_code
            })

            raise Exception(f"WHAPI API error: {error_detail}")

        except httpx.RequestError as e:
            logger.error("WHAPI request failed", extra={
                "message_id": message.id,
                "chat_id": chat.id,
                "error": str(e)
            })

            raise Exception(f"WHAPI request error: {str(e)}")

    def validate_channel_config(self, channel: Channel) -> bool:
        """Validate that channel has required WHAPI configuration."""

        if not channel.credentials_to_send_message:
            logger.warning("WHAPI channel missing credentials_to_send_message")
            return False

        credentials = channel.credentials_to_send_message
        if not isinstance(credentials, dict):
            logger.warning("WHAPI channel credentials not a dictionary")
            return False

        # Check required fields
        required_fields = ["token"]
        for field in required_fields:
            if not credentials.get(field):
                logger.warning(f"WHAPI channel missing required field: {field}")
                return False

        return True

    def _extract_phone_number(self, chat: Chat) -> str:
        """Extract phone number from chat external_id."""

        phone_number = chat.external_id

        if not phone_number:
            return ""

        # Remove any non-numeric characters except the leading +
        # WHAPI expects numbers without the + prefix
        cleaned_number = ''.join(c for c in phone_number if c.isdigit())

        return cleaned_number

    def _calculate_typing_time(self, message_content: str) -> int:
        """Calculate typing time based on message length."""

        # Base calculation: ~60 words per minute, ~5 characters per word
        # So ~5 characters per second
        character_count = len(message_content)
        base_time = max(1, character_count // 5)  # At least 1 second

        # Add some randomness (±20%)
        randomness = random.uniform(0.8, 1.2)
        typing_time = int(base_time * randomness)

        # Cap between 1 and 30 seconds to be realistic
        typing_time = max(1, min(30, typing_time))

        return typing_time

    async def _should_apply_conversation_delay(self, chat: Chat) -> bool:
        """
        Determine if we should apply conversation delay based on recent message patterns.

        Apply delay when:
        - User reactivates conversation after >1h of their last message
        - User starts new conversation

        No delay when:
        - We are in active conversation (messages exchanged in last hour)
        - We initiated the conversation
        """

        try:
            # Import here to avoid circular imports
            from database import engine

            # Get recent messages (last 3 in past hour)
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

            with Session(engine) as session:
                recent_messages_stmt = (
                    select(Message)
                    .where(Message.chat_id == chat.id)
                    .where(Message.timestamp >= one_hour_ago)
                    .order_by(Message.timestamp.desc())
                    .limit(3)
                )
                recent_messages = session.exec(recent_messages_stmt).all()

            if not recent_messages:
                # No recent messages - check if this is completely new or reactivation
                with Session(engine) as session:
                    last_contact_stmt = (
                        select(Message)
                        .where(Message.chat_id == chat.id)
                        .where(Message.sender_type == SenderType.CONTACT)
                        .order_by(Message.timestamp.desc())
                        .limit(1)
                    )
                    last_contact_msg = session.exec(last_contact_stmt).first()

                if not last_contact_msg:
                    # Completely new conversation, no delay needed (we're initiating)
                    return False

                # Check if last contact message was >1h ago (reactivation)
                time_since_contact = datetime.now(timezone.utc) - last_contact_msg.timestamp
                return time_since_contact > timedelta(hours=1)

            # Analyze recent messages
            contact_messages = [m for m in recent_messages if m.sender_type == SenderType.CONTACT]
            our_messages = [m for m in recent_messages if m.sender_type in [SenderType.USER, SenderType.AGENT]]

            if not contact_messages:
                # No recent contact messages, we're initiating - no delay
                return False

            last_contact_msg = contact_messages[0]  # Most recent contact message

            if our_messages:
                last_our_msg = our_messages[0]  # Most recent our message
                if last_our_msg.timestamp > last_contact_msg.timestamp:
                    # We already responded to their last message - no delay
                    return False

            # Check if this is reactivation (contact's last message was >1h after their previous)
            if len(contact_messages) > 1:
                previous_contact_msg = contact_messages[1]
                gap_between_contact_msgs = last_contact_msg.timestamp - previous_contact_msg.timestamp

                if gap_between_contact_msgs > timedelta(hours=1):
                    # User reactivated conversation after >1h gap
                    logger.info("Detected conversation reactivation", extra={
                        "chat_id": chat.id,
                        "gap_hours": gap_between_contact_msgs.total_seconds() / 3600
                    })
                    return True

            # Check if this is first response to contact (we haven't responded yet)
            if not our_messages:
                logger.info("Detected first response to contact message", extra={
                    "chat_id": chat.id,
                    "contact_message_time": last_contact_msg.timestamp.isoformat()
                })
                return True

            # Active conversation - no delay
            return False

        except Exception as e:
            logger.warning("Failed to analyze conversation delay", extra={
                "chat_id": chat.id,
                "error": str(e)
            })
            # Default to no delay on error
            return False

    def _get_conversation_delay(self) -> int:
        """Get random delay between 10 seconds and 2 minutes."""

        # Random delay between 10 seconds and 2 minutes (120 seconds)
        delay_seconds = random.randint(10, 120)
        return delay_seconds