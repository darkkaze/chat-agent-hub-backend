from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from models.channels import SenderType, DeliveryStatus


class ChatResponse(BaseModel):
    """Response model for chat information."""
    id: str
    name: str
    external_id: Optional[str] = None
    channel_id: str
    assigned_user_id: Optional[str] = None
    last_message_ts: datetime
    last_sender_type: Optional[SenderType] = None
    last_message: Optional[str] = None
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Response model for message information."""
    id: str
    external_id: Optional[str] = None
    chat_id: str
    content: str
    sender_type: SenderType
    timestamp: datetime
    meta_data: Dict[str, Any] = Field(default_factory=dict)
    readed: bool
    delivery_status: Optional[DeliveryStatus] = None
    
    class Config:
        from_attributes = True


class ChatListResponse(BaseModel):
    """Response model for paginated chat list."""
    chats: List[ChatResponse]
    total_count: int
    has_more: bool


class ChatMessagesResponse(BaseModel):
    """Response model for paginated chat messages."""
    messages: List[MessageResponse]
    total_count: int
    has_more: bool


class AssignChatRequest(BaseModel):
    """Request model for assigning chat to user."""
    user_id: str


class SendMessageRequest(BaseModel):
    """Request model for sending message to chat."""
    content: str = Field(min_length=1, description="Message content cannot be empty")
    meta_data: Dict[str, Any] = Field(default_factory=dict)