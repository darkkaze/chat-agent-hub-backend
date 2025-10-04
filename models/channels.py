from sqlmodel import SQLModel, Field, Column, Relationship, UniqueConstraint
from sqlalchemy import JSON
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from .helper import id_generator
from .auth import Agent


class PlatformType(str, Enum):
    """Available platform types for channels."""
    WHATSAPP = "WHATSAPP"
    WHATSAPP_TWILIO = "WHATSAPP_TWILIO"
    WHAPI = "WHAPI"
    TELEGRAM = "TELEGRAM"
    INSTAGRAM = "INSTAGRAM"


class SenderType(str, Enum):
    """Message sender types."""
    CONTACT = "CONTACT"
    USER = "USER"
    AGENT = "AGENT"


class DeliveryStatus(str, Enum):
    """Message delivery status for external platforms."""
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class Channel(SQLModel, table=True):
    """Represents each connection point (WhatsApp number, Telegram account, etc.)."""
    id: str = Field(default_factory=id_generator('channel', 10), primary_key=True)
    name: str = Field(index=True)
    platform: PlatformType
    credentials_to_send_message: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    api_to_send_message: Optional[str] = Field(default=None)


class UserChannelPermission(SQLModel, table=True):
    """Intermediate table to handle MEMBER user permissions on channels."""
    user_id: str = Field(foreign_key="user.id", primary_key=True)
    channel_id: str = Field(foreign_key="channel.id", primary_key=True)


class Chat(SQLModel, table=True):
    """Conversation with a Contact within a Channel."""
    id: str = Field(default_factory=id_generator('chat', 10), primary_key=True)
    name: str = Field(index=True)
    external_id: Optional[str] = Field(default=None, index=True)
    channel_id: str = Field(foreign_key="channel.id", index=True)
    assigned_user_id: Optional[str] = Field(default=None, foreign_key="user.id", index=True)
    last_message_ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    last_sender_type: Optional[SenderType] = Field(default=None, index=True)
    last_message: Optional[str] = Field(default=None)
    meta_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    extra_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    # Relationships
    chat_agents: list["ChatAgent"] = Relationship(back_populates="chat")


class Message(SQLModel, table=True):
    """Individual message within a Chat."""
    id: str = Field(default_factory=id_generator('message', 10), primary_key=True)
    external_id: Optional[str] = Field(default=None, index=True)
    chat_id: str = Field(foreign_key="chat.id", index=True)
    content: str
    sender_type: SenderType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    meta_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    readed: bool = Field(default=False)
    delivery_status: Optional[DeliveryStatus] = Field(default=None, index=True)



class ChatAgent(SQLModel, table=True):
    """Junction table linking chats to agents."""
    __table_args__ = (
        UniqueConstraint('chat_id', 'agent_id', name='uq_chat_agent'),
    )

    id: str = Field(default_factory=id_generator('chatagent', 10), primary_key=True)
    chat_id: str = Field(foreign_key="chat.id", index=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    active: bool = Field(default=True, index=True)

    # Relationships
    agent: Optional["Agent"] = Relationship(back_populates="chat_agents")
    chat: Optional[Chat] = Relationship(back_populates="chat_agents")