from pydantic import BaseModel, Field
from models.channels import PlatformType
from typing import Dict, Any, Optional


class CreateChannelRequest(BaseModel):
    """Schema for creating a new channel."""
    name: str = Field(..., description="Channel name")
    platform: PlatformType = Field(..., description="Platform type (WHATSAPP, TELEGRAM, INSTAGRAM)")
    credentials_to_send_message: Optional[Dict[str, Any]] = Field(default=None, description="Platform-specific credentials to send messages")
    api_to_send_message: Optional[str] = Field(default=None, description="API endpoint to send messages")


class UpdateChannelRequest(BaseModel):
    """Schema for updating channel information."""
    name: Optional[str] = Field(default=None, description="New channel name")
    credentials_to_send_message: Optional[Dict[str, Any]] = Field(default=None, description="New platform-specific credentials to send messages")
    api_to_send_message: Optional[str] = Field(default=None, description="New API endpoint to send messages")


class ChannelResponse(BaseModel):
    """Schema for channel responses (excludes sensitive credential information)."""
    id: str = Field(..., description="Channel ID")
    name: str = Field(..., description="Channel name")
    platform: PlatformType = Field(..., description="Platform type (WHATSAPP, TELEGRAM, INSTAGRAM)")
    api_to_send_message: Optional[str] = Field(default=None, description="API endpoint to send messages")

    model_config = {"from_attributes": True}  # Allows Pydantic to work with SQLModel objects


class ChannelCredentialsResponse(BaseModel):
    """Schema for channel credentials (admin only)."""
    channel_id: str = Field(..., description="Channel ID")
    channel_name: str = Field(..., description="Channel name")
    credentials_to_send_message: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific credentials to send messages")