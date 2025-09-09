from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Schema for user login."""
    username: str = Field(..., description="Username for authentication")
    password: str = Field(..., description="Plain text password")


class LoginResponse(BaseModel):
    """Schema for login response."""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(default=None, description="JWT refresh token for token renewal")
    token_type: str = Field(default="bearer", description="Token type")
    expires_at: datetime = Field(..., description="When the access token expires")
    user: "UserResponse" = Field(..., description="Authenticated user information")


class CreateAgentRequest(BaseModel):
    """Schema for creating a new external agent."""
    name: str = Field(..., description="Agent name")
    callback_url: str = Field(..., description="URL where the agent will receive callbacks")
    channel_id: Optional[str] = Field(default=None, description="Channel ID to associate the agent with (optional)")
    is_fire_and_forget: bool = Field(default=False, description="Whether the agent operates in fire-and-forget mode")
    is_active: bool = Field(default=True, description="Whether the agent is active")


class CreateUserRequest(BaseModel):
    """Schema for creating a new user."""
    username: str = Field(..., description="Unique username")
    password: str = Field(..., description="User password")
    email: Optional[str] = Field(default=None, description="User email address")
    phone: Optional[str] = Field(default=None, description="User phone number")
    role: Optional[str] = Field(default="MEMBER", description="User role (ADMIN or MEMBER)")
    is_active: bool = Field(default=True, description="Whether the user is active")


class SignupRequest(BaseModel):
    """Schema for initial admin signup (only when no users exist)."""
    username: str = Field(..., description="Admin username")
    password: str = Field(..., description="Admin password")
    email: Optional[str] = Field(default=None, description="Admin email address")


class UpdateUserRequest(BaseModel):
    """Schema for updating user information."""
    username: Optional[str] = Field(default=None, description="New username")
    password: Optional[str] = Field(default=None, description="New password")
    email: Optional[str] = Field(default=None, description="New email address")
    phone: Optional[str] = Field(default=None, description="New phone number")
    role: Optional[str] = Field(default=None, description="New user role")
    is_active: Optional[bool] = Field(default=None, description="New active status")


class UpdateAgentRequest(BaseModel):
    """Schema for updating agent information."""
    name: Optional[str] = Field(default=None, description="New agent name")
    callback_url: Optional[str] = Field(default=None, description="New callback URL")
    channel_id: Optional[str] = Field(default=None, description="New channel ID to associate the agent with")
    is_fire_and_forget: Optional[bool] = Field(default=None, description="New fire-and-forget mode setting")
    is_active: Optional[bool] = Field(default=None, description="New active status")


# Response Schemas
class UserResponse(BaseModel):
    """Schema for user responses (excludes sensitive information)."""
    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: Optional[str] = Field(default=None, description="User email address")
    phone: Optional[str] = Field(default=None, description="User phone number")
    role: str = Field(..., description="User role (ADMIN or MEMBER)")
    is_active: bool = Field(..., description="Whether the user is active")

    model_config = {"from_attributes": True}  # Allows Pydantic to work with SQLModel objects


class AgentResponse(BaseModel):
    """Schema for agent responses."""
    id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    callback_url: str = Field(..., description="Agent callback URL")
    is_fire_and_forget: bool = Field(..., description="Whether the agent operates in fire-and-forget mode")
    is_active: bool = Field(..., description="Whether the agent is active")

    model_config = {"from_attributes": True}  # Allows Pydantic to work with SQLModel objects


class MessageResponse(BaseModel):
    """Schema for simple message responses."""
    message: str = Field(..., description="Response message")