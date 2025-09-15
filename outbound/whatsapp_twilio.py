import httpx
from typing import Dict, Any
from models.channels import Chat, Message, Channel
from .base import OutboundHandler
from settings import logger


class TwilioOutboundHandler(OutboundHandler):
    """Handler for sending WhatsApp messages via Twilio API."""
    
    async def send_message(self, chat: Chat, message: Message, channel: Channel) -> Dict[str, Any]:
        """Send message to WhatsApp via Twilio API."""
        
        logger.info("Sending WhatsApp message via Twilio", extra={
            "chat_id": chat.id,
            "message_id": message.id,
            "channel_id": channel.id
        })
        
        # Validate channel configuration
        if not self.validate_channel_config(channel):
            raise ValueError("Invalid Twilio channel configuration")
        
        # Extract credentials
        credentials = channel.credentials_to_send_message
        account_sid = credentials.get("user")  # AC... format
        auth_token = credentials.get("token")
        
        # Extract phone numbers from chat metadata and channel config
        to_number = chat.external_id  # Should be the contact's phone number
        from_number = self._extract_twilio_from_number(channel, credentials)
        
        if not to_number:
            raise ValueError("No recipient phone number found in chat")
        
        # Prepare API request
        url = channel.api_to_send_message or f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Prepare form data (as per Twilio API)
        form_data = {
            "To": f"whatsapp:{to_number}",
            "From": f"whatsapp:{from_number}",
            "Body": message.content
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info("Calling Twilio API", extra={
                    "url": url,
                    "to": f"whatsapp:{to_number}",
                    "from": f"whatsapp:{from_number}",
                    "account_sid": account_sid
                })
                
                response = await client.post(url, headers=headers, data=form_data, auth=(account_sid, auth_token))
                
                logger.info("Twilio API response", extra={
                    "message_id": message.id,
                    "status_code": response.status_code,
                    "response_headers": dict(response.headers),
                    "response_text": response.text[:500]  # Limit response text for logging
                })
                
                try:
                    response_data = response.json()
                except Exception as json_error:
                    logger.error("Failed to parse Twilio response as JSON", extra={
                        "message_id": message.id,
                        "status_code": response.status_code,
                        "response_text": response.text,
                        "json_error": str(json_error)
                    })
                    response_data = {"error": "Invalid JSON response", "raw_response": response.text}
                
                if response.status_code == 201:  # Twilio success status
                    logger.info("Message sent successfully to Twilio", extra={
                        "message_id": message.id,
                        "twilio_sid": response_data.get("sid"),
                        "status": response_data.get("status")
                    })
                    
                    return {
                        "status": "success",
                        "external_id": response_data.get("sid"),
                        "platform_status": response_data.get("status"),
                        "platform_response": response_data,
                        "to": to_number,
                        "from": from_number
                    }
                else:
                    logger.error("Twilio API error", extra={
                        "message_id": message.id,
                        "status_code": response.status_code,
                        "response": response_data
                    })
                    
                    return {
                        "status": "error",
                        "error": response_data.get("message", "Unknown Twilio error"),
                        "error_code": response_data.get("code"),
                        "platform_response": response_data
                    }
                    
        except httpx.TimeoutException:
            logger.error("Twilio API timeout", extra={"message_id": message.id})
            return {
                "status": "error",
                "error": "Twilio API timeout",
                "error_type": "timeout"
            }
        except Exception as e:
            logger.error("Unexpected error sending to Twilio", extra={
                "message_id": message.id,
                "error": str(e)
            }, exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "error_type": "unexpected"
            }
    
    def validate_channel_config(self, channel: Channel) -> bool:
        """Validate that channel has required Twilio configuration."""
        if not channel.credentials_to_send_message:
            return False
        
        credentials = channel.credentials_to_send_message
        required_fields = ["user", "token"]
        
        # Check required credentials
        if not all(field in credentials for field in required_fields):
            return False
        
        # Validate account SID format (starts with AC)
        account_sid = credentials.get("user", "")
        if not account_sid.startswith("AC"):
            return False
        
        return True
    
    def _extract_twilio_from_number(self, channel: Channel, credentials: Dict[str, Any]) -> str:
        """Extract the Twilio phone number to use as 'From'."""
        
        # Try to get from credentials
        from_number = credentials.get("from_number")
        if from_number:
            return from_number
        
        # Default Twilio sandbox number (for testing)
        # In production, this should be configured properly
        logger.warning("No Twilio 'from' number configured, using default sandbox", extra={
            "channel_id": channel.id
        })
        return "+14155238886"  # Twilio's default sandbox number