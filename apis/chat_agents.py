from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, desc
from database import get_session
from models.auth import Token, Agent
from models.channels import Channel, Chat, ChatAgent
from helpers.auth import get_auth_token, require_user_or_agent, check_channel_access
from .schemas.chat_agents import ChatAgentResponse, ChatAgentListResponse, UpdateChatAgentRequest
from typing import List, Optional, Dict, Any

router = APIRouter(tags=["chat-agents"])


@router.get("/channels/{channel_id}/chats/{chat_id}/agents", response_model=ChatAgentListResponse)
async def list_chat_agents(
    channel_id: str,
    chat_id: str,
    limit: int = Query(default=50, description="Number of agents to retrieve", ge=1, le=100),
    offset: int = Query(default=0, description="Number of agents to skip", ge=0),
    active: Optional[bool] = True,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChatAgentListResponse:
    """Get paginated list of agents assigned to a chat."""

    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)

    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check channel access
    check_channel_access(token, channel, db_session)

    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")

    # Build base query for chat agents
    base_statement = select(ChatAgent).where(ChatAgent.chat_id == chat_id)

    # Apply active filter if provided
    if active is not None:
        base_statement = base_statement.where(ChatAgent.active == active)

    # Get total count with filters applied
    total_count = len(db_session.exec(base_statement).all())

    # Apply pagination and order by agent name (via join)
    from sqlmodel import join
    paginated_statement = (
        base_statement
        .join(Agent, ChatAgent.agent_id == Agent.id)
        .order_by(Agent.name)
        .offset(offset)
        .limit(limit)
    )
    chat_agents = db_session.exec(paginated_statement).all()

    # Check if there are more agents
    has_more = (offset + len(chat_agents)) < total_count

    return ChatAgentListResponse(
        chat_agents=[ChatAgentResponse.model_validate(chat_agent) for chat_agent in chat_agents],
        total_count=total_count,
        has_more=has_more
    )


@router.get("/channels/{channel_id}/chats/{chat_id}/agents/{agent_id}", response_model=ChatAgentResponse)
async def get_chat_agent(
    channel_id: str,
    chat_id: str,
    agent_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChatAgentResponse:
    """Get specific agent assigned to a chat."""

    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)

    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check channel access
    check_channel_access(token, channel, db_session)

    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")

    # Get the chat agent relationship
    chat_agent_statement = select(ChatAgent).where(
        ChatAgent.chat_id == chat_id,
        ChatAgent.agent_id == agent_id
    )
    chat_agent = db_session.exec(chat_agent_statement).first()

    if not chat_agent:
        raise HTTPException(status_code=404, detail="Agent not assigned to this chat")

    return ChatAgentResponse.model_validate(chat_agent)


@router.put("/channels/{channel_id}/chats/{chat_id}/agents/{agent_id}", response_model=ChatAgentResponse)
async def update_chat_agent(
    channel_id: str,
    chat_id: str,
    agent_id: str,
    update_data: UpdateChatAgentRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChatAgentResponse:
    """Update agent assignment for a chat (primarily active status)."""

    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)

    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Check channel access
    check_channel_access(token, channel, db_session)

    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")

    # Get the chat agent relationship
    chat_agent_statement = select(ChatAgent).where(
        ChatAgent.chat_id == chat_id,
        ChatAgent.agent_id == agent_id
    )
    chat_agent = db_session.exec(chat_agent_statement).first()

    if not chat_agent:
        raise HTTPException(status_code=404, detail="Agent not assigned to this chat")

    # Update the active status
    chat_agent.active = update_data.active
    db_session.add(chat_agent)
    db_session.commit()
    db_session.refresh(chat_agent)

    return ChatAgentResponse.model_validate(chat_agent)