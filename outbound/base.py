from abc import ABC, abstractmethod
from typing import Dict, Any
from models.channels import Chat, Message, Channel, PlatformType
from settings import logger


class OutboundHandler(ABC):
    """Base interface for sending messages to external platforms."""
    
    @abstractmethod
    async def send_message(self, chat: Chat, message: Message, channel: Channel) -> Dict[str, Any]:
        """
        Send message to external platform.
        
        Args:
            chat: Chat where message belongs
            message: Message to send
            channel: Channel with platform credentials and config
            
        Returns:
            Dict with send result and external platform response
        """
        pass
    
    @abstractmethod
    def validate_channel_config(self, channel: Channel) -> bool:
        """Validate that channel has required configuration for this platform."""
        pass


class OutboundHandlerFactory:
    """Factory to create appropriate outbound handlers based on platform."""
    
    @staticmethod
    def get_handler(platform: PlatformType) -> OutboundHandler:
        """Get the appropriate outbound handler for the platform."""
        
        if platform == PlatformType.WHATSAPP_TWILIO:
            from .whatsapp_twilio import TwilioOutboundHandler
            return TwilioOutboundHandler()
        elif platform == PlatformType.TELEGRAM:
            # Future implementation
            raise NotImplementedError(f"Outbound handler for {platform} not implemented yet")
        elif platform == PlatformType.INSTAGRAM:
            # Future implementation
            raise NotImplementedError(f"Outbound handler for {platform} not implemented yet")
        else:
            raise ValueError(f"Unsupported platform: {platform}")