from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from sqlalchemy import text
from database import get_session
from models.auth import Agent, Token
from models.channels import Channel
from .schemas.auth import CreateAgentRequest, UpdateAgentRequest, AgentResponse, MessageResponse
from helpers.auth import get_auth_token, require_admin

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/")
async def create_agent(
    agent_data: CreateAgentRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> AgentResponse:
    """Create new external agent and associate to channel (Admins only)."""
    
    # Validate admin access
    await require_admin(token=token)
    
    # Create agent with validated data
    new_agent = Agent(
        name=agent_data.name,
        webhook_url=agent_data.webhook_url,
        is_fire_and_forget=agent_data.is_fire_and_forget,
        buffer_time_seconds=agent_data.buffer_time_seconds,
        history_msg_count=agent_data.history_msg_count,
        recent_msg_window_minutes=agent_data.recent_msg_window_minutes,
        activate_for_new_conversation=agent_data.activate_for_new_conversation,
        is_active=agent_data.is_active
    )
    
    db_session.add(new_agent)
    db_session.commit()
    db_session.refresh(new_agent)

    # Auto-assign agent to existing chats if activate_for_new_conversation is True
    if new_agent.activate_for_new_conversation:
        bulk_insert_query = text("""
            INSERT INTO chatagent (id, chat_id, agent_id, active)
            SELECT
                CONCAT('chatagent_', SUBSTRING(MD5(RANDOM()::text || CLOCK_TIMESTAMP()::text) FROM 1 FOR 10)),
                c.id,
                :agent_id,
                true
            FROM chat c
            ON CONFLICT (chat_id, agent_id) DO NOTHING
        """)
        db_session.exec(bulk_insert_query, params={"agent_id": new_agent.id})
        db_session.commit()

    return AgentResponse.model_validate(new_agent)


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    agent_data: UpdateAgentRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> AgentResponse:
    """Update agent information (Admins only)."""
    
    # Validate admin access
    await require_admin(token=token)
    
    # Get the agent to update
    agent_statement = select(Agent).where(Agent.id == agent_id)
    agent = db_session.exec(agent_statement).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Note: Channel verification removed per model changes
    
    # Update agent fields that are provided (only non-None values)
    if agent_data.name is not None:
        agent.name = agent_data.name
    if agent_data.webhook_url is not None:
        agent.webhook_url = agent_data.webhook_url
    if agent_data.is_fire_and_forget is not None:
        agent.is_fire_and_forget = agent_data.is_fire_and_forget
    if agent_data.buffer_time_seconds is not None:
        agent.buffer_time_seconds = agent_data.buffer_time_seconds
    if agent_data.history_msg_count is not None:
        agent.history_msg_count = agent_data.history_msg_count
    if agent_data.recent_msg_window_minutes is not None:
        agent.recent_msg_window_minutes = agent_data.recent_msg_window_minutes
    if agent_data.activate_for_new_conversation is not None:
        agent.activate_for_new_conversation = agent_data.activate_for_new_conversation
    if agent_data.is_active is not None:
        agent.is_active = agent_data.is_active
    
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    # Note: Channel-Agent association removed per model changes
    
    return AgentResponse.model_validate(agent)


@router.get("/")
async def list_agents(
    is_active: bool = True,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> list[AgentResponse]:
    """List all agents filtered by active status."""
    
    # Get agents filtered by is_active status
    agent_statement = select(Agent).where(Agent.is_active == is_active)
    agents = db_session.exec(agent_statement).all()
    
    # Return agents without sensitive information
    return [AgentResponse.model_validate(agent) for agent in agents]


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    hard: bool = False,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MessageResponse:
    """Delete an agent (Admins only). 
    Soft delete (default) sets is_active=False, hard delete removes from database
    """
    
    # Validate admin access
    await require_admin(token=token)
    
    # Get the agent to delete
    agent_statement = select(Agent).where(Agent.id == agent_id)
    agent = db_session.exec(agent_statement).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    if hard:
        # Hard delete - remove agent from database
        db_session.delete(agent)
        db_session.commit()
        return MessageResponse(message="Agent deleted successfully")
    else:
        # Soft delete - mark as inactive
        agent.is_active = False
        db_session.add(agent)
        db_session.commit()
        return MessageResponse(message="Agent soft-deleted successfully")