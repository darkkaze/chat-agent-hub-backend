from sqlmodel import Session
from models.channels import Chat, Message, Channel
from .base import OutboundHandlerFactory
from settings import logger


class MessageSender:
    """Service to handle sending messages to external platforms with error handling and metadata updates."""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    async def send_to_platform(self, chat: Chat, message: Message, channel: Channel) -> None:
        """
        Send message to external platform and update message metadata.
        
        This method handles all the complexity of:
        - Getting the right platform handler
        - Sending the message
        - Updating metadata with results/errors
        - Logging success/failures
        
        Args:
            chat: Chat where message belongs
            message: Message to send (will be updated with metadata)
            channel: Channel with platform credentials and config
        """
        
        try:
            outbound_handler = OutboundHandlerFactory.get_handler(channel.platform)
            send_result = await outbound_handler.send_message(chat, message, channel)
            
            # Update message metadata with platform response
            if send_result.get("status") == "success":
                # Update external_id with platform's message ID
                if send_result.get("external_id"):
                    message.external_id = send_result["external_id"]
                
                # Add platform response to metadata
                message.meta_data.update({
                    "platform_sent": True,
                    "platform_status": send_result.get("platform_status"),
                    "platform_external_id": send_result.get("external_id"),
                    "sent_to": send_result.get("to"),
                    "sent_from": send_result.get("from")
                })
                
                logger.info("Message sent to platform successfully", extra={
                    "message_id": message.id,
                    "platform": channel.platform,
                    "external_id": send_result.get("external_id")
                })
            else:
                # Log error but don't fail the API
                message.meta_data.update({
                    "platform_sent": False,
                    "platform_error": send_result.get("error"),
                    "platform_error_code": send_result.get("error_code"),
                    "platform_error_type": send_result.get("error_type")
                })
                
                logger.error("Failed to send message to platform", extra={
                    "message_id": message.id,
                    "platform": channel.platform,
                    "error": send_result.get("error")
                })
            
        except (NotImplementedError, ValueError) as e:
            # Platform not supported or configuration error
            logger.warning("Platform send not available", extra={
                "message_id": message.id,
                "platform": channel.platform,
                "error": str(e)
            })
            
            # Update metadata to indicate platform send was not attempted
            message.meta_data.update({
                "platform_sent": False,
                "platform_error": str(e),
                "platform_error_type": "not_supported"
            })
            
        except Exception as e:
            # Unexpected error - log but don't fail the API
            logger.error("Unexpected error sending to platform", extra={
                "message_id": message.id,
                "platform": channel.platform,
                "error": str(e)
            }, exc_info=True)
            
            message.meta_data.update({
                "platform_sent": False,
                "platform_error": "Unexpected error during send",
                "platform_error_type": "unexpected"
            })
        
        # Save metadata updates
        self.db_session.add(message)
        self.db_session.commit()
        self.db_session.refresh(message)