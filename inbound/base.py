from abc import ABC, abstractmethod
from typing import Dict, Any
from sqlmodel import Session
from models.channels import PlatformType, Chat, Message
from settings import logger


class InboundHandler(ABC):
    """Base interface for platform inbound message handlers."""
    
    def __init__(self, session: Session):
        self.session = session
    
    @abstractmethod
    async def process_inbound(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """
        Process inbound message data and create Chat/Message records.

        Args:
            data: Raw payload from platform
            channel_id: ID of the channel receiving the message

        Returns:
            Dict with processing result and created entities
        """
        pass
    
    @abstractmethod
    def validate_payload(self, data: Dict[str, Any]) -> bool:
        """Validate that the payload has required fields for this platform."""
        pass
    
    @abstractmethod
    def extract_message_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized message data from platform-specific payload."""
        pass


class InboundHandlerFactory:
    """Factory to create appropriate inbound message handlers based on platform."""

    @staticmethod
    def get_handler(platform: PlatformType, session: Session) -> InboundHandler:
        """Get the appropriate inbound handler for the platform."""

        if platform == PlatformType.WHATSAPP_TWILIO:
            from .whatsapp_twilio import WhatsAppTwilioHandler
            return WhatsAppTwilioHandler(session)
        elif platform == PlatformType.WHAPI:
            from .whapi import WhapiHandler
            return WhapiHandler(session)
        elif platform == PlatformType.TELEGRAM:
            from .telegram import TelegramHandler
            return TelegramHandler(session)
        elif platform == PlatformType.INSTAGRAM:
            # Future implementation
            raise NotImplementedError(f"Handler for {platform} not implemented yet")
        else:
            raise ValueError(f"Unsupported platform: {platform}")