from sqlmodel import SQLModel, Field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from .helper import id_generator


class PlatformType(str, Enum):
    """Available platform types for channels."""
    WHATSAPP = "WHATSAPP"
    TELEGRAM = "TELEGRAM"
    INSTAGRAM = "INSTAGRAM"


class SenderType(str, Enum):
    """Message sender types."""
    CONTACT = "CONTACT"
    USER = "USER"
    AGENT = "AGENT"


class Channel(SQLModel, table=True):
    """Represents each connection point (WhatsApp number, Telegram account, etc.)."""
    id: str = Field(default_factory=id_generator('channel', 10), primary_key=True)
    name: str = Field(index=True)
    platform: PlatformType
    credentials: Dict[str, Any] = Field(default_factory=dict, sa_type=dict)


class UserChannelPermission(SQLModel, table=True):
    """Intermediate table to handle MEMBER user permissions on channels."""
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    channel_id: str = Field(foreign_key="channel.id", primary_key=True)


class Chat(SQLModel, table=True):
    """Conversation with a Contact within a Channel."""
    id: str = Field(default_factory=id_generator('chat', 10), primary_key=True)
    external_id: Optional[str] = Field(default=None, index=True)
    channel_id: str = Field(foreign_key="channel.id", index=True)
    contact_id: Optional[str] = Field(default=None, foreign_key="contact.id", index=True)
    assigned_user_id: Optional[str] = Field(default=None, foreign_key="user.id", index=True)
    metadata: Dict[str, Any] = Field(default_factory=dict, sa_type=dict)


class Message(SQLModel, table=True):
    """Individual message within a Chat."""
    id: str = Field(default_factory=id_generator('message', 10), primary_key=True)
    external_id: Optional[str] = Field(default=None, index=True)
    chat_id: str = Field(foreign_key="chat.id", index=True)
    content: str
    sender_type: SenderType
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    metadata: Dict[str, Any] = Field(default_factory=dict, sa_type=dict)
    readed: bool = Field(default=False)