from sqlmodel import SQLModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime
from .helper import id_generator


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


class Token(SQLModel, table=True):
    """JWT token information for user sessions."""
    id: str = Field(default_factory=id_generator('token', 10), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    token_type: str = Field(default="bearer")
    access_token: str = Field(unique=True, index=True)
    refresh_token: Optional[str] = Field(default=None, unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_revoked: bool = Field(default=False)