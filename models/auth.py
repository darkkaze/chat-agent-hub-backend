from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .helper import id_generator

if TYPE_CHECKING:
    from .channels import ChannelAgent, ChatAgent


class UserRole(str, Enum):
    """Available roles for system users."""
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class User(SQLModel, table=True):
    """Internal users who operate the system."""
    id: str = Field(default_factory=id_generator('user', 10), primary_key=True)
    username: str = Field(unique=True, index=True)
    email: Optional[str] = Field(default=None, unique=True, index=True)
    phone: Optional[str] = Field(default=None, unique=True, index=True)
    hashed_password: str
    role: UserRole = Field(default=UserRole.MEMBER)
    is_active: bool = Field(default=True)
    
    # Relationships
    token_users: List["TokenUser"] = Relationship(back_populates="user")


class Agent(SQLModel, table=True):
    """External service or bot that can manage conversations."""
    id: str = Field(default_factory=id_generator('agent', 10), primary_key=True)
    name: str = Field(index=True)
    callback_url: str
    is_fire_and_forget: bool = Field(default=False)
    is_active: bool = Field(default=True)
    
    # Relationships
    token_agents: List["TokenAgent"] = Relationship(back_populates="agent")
    channel_agents: List["ChannelAgent"] = Relationship(back_populates="agent")
    chat_agents: List["ChatAgent"] = Relationship(back_populates="agent")


class Token(SQLModel, table=True):
    """JWT token information for authentication sessions."""
    id: str = Field(default_factory=id_generator('token', 10), primary_key=True)
    token_type: str = Field(default="bearer")
    access_token: str = Field(unique=True, index=True)
    refresh_token: Optional[str] = Field(default=None, unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_revoked: bool = Field(default=False)
    
    # Relationships
    token_users: List["TokenUser"] = Relationship(back_populates="token")
    token_agents: List["TokenAgent"] = Relationship(back_populates="token")
    
    # Aliases for easier access
    @property
    def user(self) -> Optional["User"]:
        """Get the user associated with this token."""
        return self.token_users[0].user if self.token_users else None
    
    @property  
    def agent(self) -> Optional["Agent"]:
        """Get the agent associated with this token."""
        return self.token_agents[0].agent if self.token_agents else None


class TokenUser(SQLModel, table=True):
    """Junction table linking tokens to users."""
    id: str = Field(default_factory=id_generator('tokuser', 10), primary_key=True)
    token_id: str = Field(foreign_key="token.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    
    # Relationships
    token: Optional[Token] = Relationship(back_populates="token_users")
    user: Optional["User"] = Relationship(back_populates="token_users")


class TokenAgent(SQLModel, table=True):
    """Junction table linking tokens to agents."""
    id: str = Field(default_factory=id_generator('tokagent', 10), primary_key=True)
    token_id: str = Field(foreign_key="token.id", index=True)
    agent_id: str = Field(foreign_key="agent.id", index=True)
    
    # Relationships
    token: Optional[Token] = Relationship(back_populates="token_agents")
    agent: Optional["Agent"] = Relationship(back_populates="token_agents")
