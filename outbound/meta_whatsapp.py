import httpx
from typing import Dict, Any
from models.channels import Chat, Message, Channel
from .base import OutboundHandler
from settings import logger


class MetaOutboundHandler(OutboundHandler):
    """Handler for sending WhatsApp messages via Meta Cloud API."""

    async def send_message(self, chat: Chat, message: Message, channel: Channel) -> Dict[str, Any]:
        """Send message to WhatsApp via Meta Cloud API."""

        logger.info("Sending WhatsApp message via Meta", extra={
            "chat_id": chat.id,
            "message_id": message.id,
            "channel_id": channel.id
        })

        # Validate channel configuration
        if not self.validate_channel_config(channel):
            raise ValueError("Invalid Meta channel configuration")

        # Extract credentials
        credentials = channel.credentials_to_send_message
        token = credentials.get("token")
        phone_number_id = credentials.get("phone_number_id")

        # Extract phone number from chat
        to_number = self._extract_phone_number(chat)

        if not to_number:
            raise ValueError("No recipient phone number found in chat")

        # Prepare Meta API request
        # Default Meta Cloud API base URL
        base_url = channel.api_to_send_message or "https://graph.instagram.com/v18.0"
        url = f"{base_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Prepare request body (Meta Cloud API format)
        request_body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {
                "body": message.content
            }
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

                # Extract message ID from Meta response
                message_id = response_data.get("messages", [{}])[0].get("id")

                logger.info("Meta message sent successfully", extra={
                    "message_id": message.id,
                    "chat_id": chat.id,
                    "meta_message_id": message_id,
                    "to_number": to_number
                })

                return {
                    "status": "success",
                    "external_id": message_id,
                    "platform_status": "sent",
                    "platform_response": response_data,
                    "to": to_number,
                    "from": phone_number_id
                }

        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP {e.response.status_code}"
            try:
                error_response = e.response.json()
                error_detail = error_response.get("message", error_detail)
            except:
                pass

            logger.error("Failed to send Meta message", extra={
                "message_id": message.id,
                "chat_id": chat.id,
                "error": error_detail,
                "status_code": e.response.status_code
            })

            return {
                "status": "error",
                "error": error_detail,
                "error_code": e.response.status_code,
                "error_type": "http_error"
            }

        except httpx.RequestError as e:
            logger.error("Meta request failed", extra={
                "message_id": message.id,
                "chat_id": chat.id,
                "error": str(e)
            })

            return {
                "status": "error",
                "error": str(e),
                "error_type": "request_error"
            }

    def validate_channel_config(self, channel: Channel) -> bool:
        """Validate that channel has required Meta configuration."""

        if not channel.credentials_to_send_message:
            logger.warning("Meta channel missing credentials_to_send_message")
            return False

        credentials = channel.credentials_to_send_message
        if not isinstance(credentials, dict):
            logger.warning("Meta channel credentials not a dictionary")
            return False

        # Check required fields
        required_fields = ["token", "phone_number_id"]
        for field in required_fields:
            if not credentials.get(field):
                logger.warning(f"Meta channel missing required field: {field}")
                return False

        return True

    def _extract_phone_number(self, chat: Chat) -> str:
        """Extract phone number from chat external_id."""

        phone_number = chat.external_id

        if not phone_number:
            return ""

        # Remove any non-numeric characters (including +)
        # Meta expects numbers in E.164 format without + prefix
        cleaned_number = ''.join(c for c in phone_number if c.isdigit())

        return cleaned_number
