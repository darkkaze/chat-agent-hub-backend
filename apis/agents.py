from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models.auth import Agent, Token
from models.channels import Channel, ChannelAgent
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
    
    # Verify channel exists if provided
    if agent_data.channel_id:
        channel_statement = select(Channel).where(Channel.id == agent_data.channel_id)
        channel = db_session.exec(channel_statement).first()
        
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found"
            )
    
    # Create agent with validated data
    new_agent = Agent(
        name=agent_data.name,
        callback_url=agent_data.callback_url,
        is_fire_and_forget=agent_data.is_fire_and_forget,
        is_active=agent_data.is_active
    )
    
    db_session.add(new_agent)
    db_session.commit()
    db_session.refresh(new_agent)
    
    # Associate agent to channel if provided
    if agent_data.channel_id:
        channel_agent = ChannelAgent(channel_id=agent_data.channel_id, agent_id=new_agent.id)
        db_session.add(channel_agent)
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
    
    # Verify new channel exists if provided
    if agent_data.channel_id is not None:
        if agent_data.channel_id:  # Not empty string
            channel_statement = select(Channel).where(Channel.id == agent_data.channel_id)
            channel = db_session.exec(channel_statement).first()
            
            if not channel:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Channel not found"
                )
    
    # Update agent fields that are provided (only non-None values)
    if agent_data.name is not None:
        agent.name = agent_data.name
    if agent_data.callback_url is not None:
        agent.callback_url = agent_data.callback_url
    if agent_data.is_fire_and_forget is not None:
        agent.is_fire_and_forget = agent_data.is_fire_and_forget
    if agent_data.is_active is not None:
        agent.is_active = agent_data.is_active
    
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    
    # Handle channel association update
    if agent_data.channel_id is not None:
        # Remove existing channel associations
        existing_associations = db_session.exec(
            select(ChannelAgent).where(ChannelAgent.agent_id == agent_id)
        ).all()
        for association in existing_associations:
            db_session.delete(association)
        
        # Add new channel association if provided
        if agent_data.channel_id:  # Not empty string
            new_association = ChannelAgent(channel_id=agent_data.channel_id, agent_id=agent_id)
            db_session.add(new_association)
        
        db_session.commit()
    
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
        # Hard delete - remove channel associations first, then agent
        existing_associations = db_session.exec(
            select(ChannelAgent).where(ChannelAgent.agent_id == agent_id)
        ).all()
        for association in existing_associations:
            db_session.delete(association)
        
        # Remove agent from database
        db_session.delete(agent)
        db_session.commit()
        return MessageResponse(message="Agent deleted successfully")
    else:
        # Soft delete - mark as inactive
        agent.is_active = False
        db_session.add(agent)
        db_session.commit()
        return MessageResponse(message="Agent soft-deleted successfully")