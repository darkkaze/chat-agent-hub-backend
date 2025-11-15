import httpx
import random
from typing import Dict, Any
from models.channels import Chat, Message, Channel
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

        # No conversation delay - keep it simple

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
        # Extract base URL from channel config, default to WHAPI base URL
        base_url = channel.api_to_send_message or "https://gate.whapi.cloud"
        # Hardcode text messages endpoint
        endpoint = "/messages/text"
        url = f"{base_url}{endpoint}"

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

