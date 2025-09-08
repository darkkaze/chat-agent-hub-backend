from pydantic import BaseModel, Field
from models.channels import PlatformType
from typing import Dict, Any


class CreateChannelRequest(BaseModel):
    """Schema for creating a new channel."""
    name: str = Field(..., description="Channel name")
    platform: PlatformType = Field(..., description="Platform type (WHATSAPP, TELEGRAM, INSTAGRAM)")
    credentials: Dict[str, Any] = Field(..., description="Platform-specific credentials")


class ChannelResponse(BaseModel):
    """Schema for channel responses (excludes sensitive credential information)."""
    id: str = Field(..., description="Channel ID")
    name: str = Field(..., description="Channel name")
    platform: PlatformType = Field(..., description="Platform type (WHATSAPP, TELEGRAM, INSTAGRAM)")

    model_config = {"from_attributes": True}  # Allows Pydantic to work with SQLModel objects