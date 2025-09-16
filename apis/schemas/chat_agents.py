from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AgentInfo(BaseModel):
    """Basic agent information for responses."""
    id: str
    name: str
    webhook_url: Optional[str] = None
    is_active: bool
    buffer_time_seconds: int
    history_msg_count: int
    recent_msg_window_minutes: int
    activate_for_new_conversation: bool
    is_fire_and_forget: bool

    class Config:
        from_attributes = True


class ChatAgentResponse(BaseModel):
    """Response model for chat agent relationship."""
    id: str
    chat_id: str
    agent_id: str
    active: bool
    agent: AgentInfo

    class Config:
        from_attributes = True


class ChatAgentListResponse(BaseModel):
    """Response model for paginated chat agent list."""
    chat_agents: List[ChatAgentResponse]
    total_count: int
    has_more: bool


class UpdateChatAgentRequest(BaseModel):
    """Request model for updating chat agent."""
    active: bool = Field(description="Whether the agent should be active for this chat")