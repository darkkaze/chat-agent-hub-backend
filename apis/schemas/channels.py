from pydantic import BaseModel, Field
from models.channels import PlatformType
from typing import Dict, Any, Optional


class CreateChannelRequest(BaseModel):
    """Schema for creating a new channel."""
    name: str = Field(..., description="Channel name")
    platform: PlatformType = Field(..., description="Platform type (WHATSAPP, TELEGRAM, INSTAGRAM)")
    credentials_to_send_message: Optional[Dict[str, Any]] = Field(default=None, description="Platform-specific credentials to send messages")
    api_to_send_message: Optional[str] = Field(default=None, description="API endpoint to send messages")
    buffer_time_seconds: int = Field(default=3, description="Buffer time in seconds", ge=0, le=60)
    history_msg_count: int = Field(default=40, description="Number of messages in history", ge=1, le=200)
    recent_msg_window_minutes: int = Field(default=60*24, description="Recent messages window in minutes", ge=1)


class UpdateChannelRequest(BaseModel):
    """Schema for updating channel information."""
    name: Optional[str] = Field(default=None, description="New channel name")
    credentials_to_send_message: Optional[Dict[str, Any]] = Field(default=None, description="New platform-specific credentials to send messages")
    api_to_send_message: Optional[str] = Field(default=None, description="New API endpoint to send messages")
    buffer_time_seconds: Optional[int] = Field(default=None, description="New buffer time in seconds", ge=0, le=60)
    history_msg_count: Optional[int] = Field(default=None, description="New number of messages in history", ge=1, le=200)
    recent_msg_window_minutes: Optional[int] = Field(default=None, description="New recent messages window in minutes", ge=1)


class ChannelResponse(BaseModel):
    """Schema for channel responses (excludes sensitive credential information)."""
    id: str = Field(..., description="Channel ID")
    name: str = Field(..., description="Channel name")
    platform: PlatformType = Field(..., description="Platform type (WHATSAPP, TELEGRAM, INSTAGRAM)")
    api_to_send_message: Optional[str] = Field(default=None, description="API endpoint to send messages")
    buffer_time_seconds: int = Field(..., description="Buffer time in seconds")
    history_msg_count: int = Field(..., description="Number of messages in history")
    recent_msg_window_minutes: int = Field(..., description="Recent messages window in minutes")

    model_config = {"from_attributes": True}  # Allows Pydantic to work with SQLModel objects