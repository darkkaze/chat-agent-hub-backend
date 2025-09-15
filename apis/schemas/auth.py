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
    webhook_url: str = Field(..., description="URL where the agent will receive webhooks")
    is_fire_and_forget: bool = Field(default=False, description="Whether the agent operates in fire-and-forget mode")
    buffer_time_seconds: int = Field(default=3, description="Buffer time in seconds")
    history_msg_count: int = Field(default=40, description="Number of history messages to include")
    recent_msg_window_minutes: int = Field(default=60*24, description="Recent message window in minutes")
    activate_for_new_conversation: bool = Field(default=False, description="Whether agent activates for new conversations")
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
    webhook_url: Optional[str] = Field(default=None, description="New webhook URL")
    is_fire_and_forget: Optional[bool] = Field(default=None, description="New fire-and-forget mode setting")
    buffer_time_seconds: Optional[int] = Field(default=None, description="New buffer time in seconds")
    history_msg_count: Optional[int] = Field(default=None, description="New number of history messages to include")
    recent_msg_window_minutes: Optional[int] = Field(default=None, description="New recent message window in minutes")
    activate_for_new_conversation: Optional[bool] = Field(default=None, description="New activate for new conversation setting")
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
    webhook_url: str = Field(..., description="Agent webhook URL")
    is_fire_and_forget: bool = Field(..., description="Whether the agent operates in fire-and-forget mode")
    buffer_time_seconds: int = Field(..., description="Buffer time in seconds")
    history_msg_count: int = Field(..., description="Number of history messages to include")
    recent_msg_window_minutes: int = Field(..., description="Recent message window in minutes")
    activate_for_new_conversation: bool = Field(..., description="Whether agent activates for new conversations")
    is_active: bool = Field(..., description="Whether the agent is active")

    model_config = {"from_attributes": True}  # Allows Pydantic to work with SQLModel objects


class MessageResponse(BaseModel):
    """Schema for simple message responses."""
    message: str = Field(..., description="Response message")