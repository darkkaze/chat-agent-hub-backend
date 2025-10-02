import httpx
from typing import Dict, Any
from models.channels import Chat, Message, Channel
from .base import OutboundHandler
from settings import logger


class TelegramOutboundHandler(OutboundHandler):
    """Handler for sending Telegram messages via Telegram Bot API."""

    async def send_message(self, chat: Chat, message: Message, channel: Channel) -> Dict[str, Any]:
        """Send message to Telegram via Bot API."""

        logger.info("Sending Telegram message", extra={
            "chat_id": chat.id,
            "message_id": message.id,
            "channel_id": channel.id
        })

        # Validate channel configuration
        if not self.validate_channel_config(channel):
            raise ValueError("Invalid Telegram channel configuration")

        # Extract credentials
        credentials = channel.credentials_to_send_message
        bot_token = credentials.get("token")

        # Extract chat ID from external_id
        telegram_chat_id = chat.external_id

        if not telegram_chat_id:
            raise ValueError("No Telegram chat ID found in chat.external_id")

        # Prepare API request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        # Prepare request body
        request_body = {
            "chat_id": telegram_chat_id,
            "text": message.content,
            "parse_mode": "HTML"  # Support basic HTML formatting
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=request_body,
                    timeout=30.0
                )

                response.raise_for_status()
                response_data = response.json()

                # Check if the response is successful
                if not response_data.get("ok"):
                    error_description = response_data.get("description", "Unknown error")
                    raise Exception(f"Telegram API error: {error_description}")

                result = response_data.get("result", {})
                telegram_message_id = result.get("message_id")

                logger.info("Telegram message sent successfully", extra={
                    "message_id": message.id,
                    "chat_id": chat.id,
                    "telegram_message_id": telegram_message_id
                })

                return {
                    "status": "sent",
                    "external_id": str(telegram_message_id),
                    "platform_response": response_data,
                    "telegram_chat_id": telegram_chat_id
                }

        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP {e.response.status_code}"
            try:
                error_response = e.response.json()
                error_detail = error_response.get("description", error_detail)
            except:
                pass

            logger.error("Failed to send Telegram message", extra={
                "message_id": message.id,
                "chat_id": chat.id,
                "error": error_detail,
                "status_code": e.response.status_code
            })

            raise Exception(f"Telegram API error: {error_detail}")

        except httpx.RequestError as e:
            logger.error("Telegram request failed", extra={
                "message_id": message.id,
                "chat_id": chat.id,
                "error": str(e)
            })

            raise Exception(f"Telegram request error: {str(e)}")

    def validate_channel_config(self, channel: Channel) -> bool:
        """Validate that channel has required Telegram configuration."""

        if not channel.credentials_to_send_message:
            logger.warning("Telegram channel missing credentials_to_send_message")
            return False

        credentials = channel.credentials_to_send_message
        if not isinstance(credentials, dict):
            logger.warning("Telegram channel credentials not a dictionary")
            return False

        # Check required fields
        if not credentials.get("token"):
            logger.warning("Telegram channel missing required field: token")
            return False

        return True
