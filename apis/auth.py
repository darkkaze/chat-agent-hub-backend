from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.channels import Channel
from .schemas.auth import (
    LoginRequest, LoginResponse, CreateAgentRequest, CreateUserRequest, UpdateUserRequest, UpdateAgentRequest,
    UserResponse, AgentResponse, MessageResponse, SignupRequest, AgentTokenResponse, AgentTokensResponse
)
from helpers.auth import get_auth_token
from helpers.auth import require_admin
from helpers.auth import require_admin_or_self

import hashlib
from datetime import datetime, timedelta, timezone
from models.helper import id_generator

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/has-users")
async def has_users(
    db_session: Session = Depends(get_session)
) -> dict:
    """Check if any users exist in the system (for onboarding)."""
    
    # Count total users regardless of is_active status
    user_statement = select(User)
    users = db_session.exec(user_statement).all()
    
    return {"has_users": len(users) > 0}


@router.post("/signup")
async def signup(
    signup_data: SignupRequest,
    db_session: Session = Depends(get_session)
) -> LoginResponse:
    """Initial admin signup (only works when no users exist in system)."""
    
    # Check if any users exist
    user_statement = select(User)
    existing_users = db_session.exec(user_statement).all()
    
    if len(existing_users) > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users already exist. Signup is disabled."
        )
    
    # Hash the password
    hashed_password = hashlib.sha256(signup_data.password.encode()).hexdigest()
    
    # Create admin user
    new_user = User(
        username=signup_data.username,
        email=signup_data.email,
        hashed_password=hashed_password,
        role=UserRole.ADMIN,
        is_active=True
    )
    
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    
    # Generate tokens
    token_generator = id_generator('tkn', 32)
    refresh_generator = id_generator('ref', 32)
    
    access_token = token_generator()
    refresh_token = refresh_generator()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    # Create token record
    new_token = Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at
    )
    
    db_session.add(new_token)
    db_session.commit()
    db_session.refresh(new_token)
    
    # Link token to user
    token_user = TokenUser(token_id=new_token.id, user_id=new_user.id)
    db_session.add(token_user)
    db_session.commit()
    
    # Return login response
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_at=expires_at,
        user=UserResponse.model_validate(new_user)
    )


@router.post("/token")
async def login(
    login_data: LoginRequest,
    db_session: Session = Depends(get_session)
) -> LoginResponse:
    """Login for internal users."""
    
    # Find user by username
    user_statement = select(User).where(
        User.username == login_data.username,
        User.is_active == True  # Only allow login for active users
    )
    user = db_session.exec(user_statement).first()
    
    # Hash the provided password to compare
    hashed_password = hashlib.sha256(login_data.password.encode()).hexdigest()
    
    # Validate credentials (don't reveal whether username or password was wrong)
    if not user or user.hashed_password != hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Generate tokens
    token_generator = id_generator('tkn', 32)
    refresh_generator = id_generator('ref', 32)
    
    access_token = token_generator()
    refresh_token = refresh_generator()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)  # 24 hours expiry
    
    # Create token record
    new_token = Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at
    )
    
    db_session.add(new_token)
    db_session.commit()
    db_session.refresh(new_token)
    
    # Link token to user
    token_user = TokenUser(token_id=new_token.id, user_id=user.id)
    db_session.add(token_user)
    db_session.commit()
    
    # Return login response
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_at=expires_at,
        user=UserResponse.model_validate(user)
    )


# User management endpoints
@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> UserResponse:
    """Get user information"""
    
    # Get the user
    user_statement = select(User).where(User.id == user_id)
    user = db_session.exec(user_statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Return user data without sensitive information
    return UserResponse.model_validate(user)


@router.get("/users")
async def list_users(
    is_active: bool = True,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> list[UserResponse]:
    """List all users."""
    # Get users filtered by is_active status
    user_statement = select(User).where(User.is_active == is_active)
    users = db_session.exec(user_statement).all()
    
    # Return users without sensitive information
    return [UserResponse.model_validate(user) for user in users]


@router.post("/users")
async def create_user(
    user_data: CreateUserRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> UserResponse:
    """Create new user (Admins only)."""
    
    # Validate admin access
    await require_admin(token=token)
    
    # Hash the password
    hashed_password = hashlib.sha256(user_data.password.encode()).hexdigest()
    
    # Create user with validated data
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        phone=user_data.phone, 
        hashed_password=hashed_password,
        role=UserRole[user_data.role] if user_data.role else UserRole.MEMBER,
        is_active=user_data.is_active
    )
    
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    
    # Return user data without sensitive information
    return UserResponse.model_validate(new_user)


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    user_data: UpdateUserRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> UserResponse:
    """Update user information 
    Admins or token.user_id == user_id"""
    
    # Validate admin access or self-update
    await require_admin_or_self(token=token, user_id=user_id)
    
    # Get the user to update
    user_statement = select(User).where(User.id == user_id)
    user = db_session.exec(user_statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields that are provided (only non-None values)
    if user_data.username is not None:
        user.username = user_data.username
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.phone is not None:
        user.phone = user_data.phone
    if user_data.role is not None:
        user.role = UserRole[user_data.role]
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    # Hash password if provided
    if user_data.password is not None:
        hashed_password = hashlib.sha256(user_data.password.encode()).hexdigest()
        user.hashed_password = hashed_password
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Return user data without sensitive information
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    hard: bool = False,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MessageResponse:
    """Delete a user (Admins only). 
    Soft delete (default) sets is_active=False, hard delete removes from database
    """
    
    # Validate admin access
    await require_admin(token=token)
    
    # Get the user to delete
    user_statement = select(User).where(User.id == user_id)
    user = db_session.exec(user_statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if hard:
        # Hard delete - remove from database
        db_session.delete(user)
        db_session.commit()
        return MessageResponse(message="User deleted successfully")
    else:
        # Soft delete - mark as inactive
        user.is_active = False
        db_session.add(user)
        db_session.commit()
        return MessageResponse(message="User soft-deleted successfully")


# Agent management endpoints
@router.post("/agents")
async def create_agent(
    agent_data: CreateAgentRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> AgentResponse:
    """Create new external agent and associate to channel (Admins only)."""
    
    # Validate admin access
    await require_admin(token=token)
    
    # Note: Channel verification removed per model changes
    
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

    # Generate tokens for agent
    token_generator = id_generator('tkn', 32)
    refresh_generator = id_generator('ref', 32)

    access_token = token_generator()
    refresh_token = refresh_generator()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24*365)  # 1 year expiry for agents

    # Create token record
    new_token = Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at
    )

    db_session.add(new_token)
    db_session.commit()
    db_session.refresh(new_token)

    # Link token to agent
    token_agent = TokenAgent(token_id=new_token.id, agent_id=new_agent.id)
    db_session.add(token_agent)
    db_session.commit()

    # Note: Channel-Agent association removed per model changes

    return AgentResponse.model_validate(new_agent)


@router.put("/agents/{agent_id}")
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


@router.get("/agents")
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


@router.delete("/agents/{agent_id}")
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


@router.get("/agents/{agent_id}/tokens", response_model=AgentTokensResponse)
async def get_agent_tokens(
    agent_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> AgentTokensResponse:
    """Get active tokens for an agent (Admins only)."""

    # Validate admin access
    await require_admin(token=token)

    # Get the agent to verify it exists
    agent_statement = select(Agent).where(Agent.id == agent_id)
    agent = db_session.exec(agent_statement).first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    # Get active tokens for this agent
    current_time = datetime.now(timezone.utc)
    active_tokens_statement = (
        select(Token)
        .join(TokenAgent)
        .where(TokenAgent.agent_id == agent_id)
        .where(Token.is_revoked == False)
        .where(Token.expires_at > current_time)
    )

    active_tokens = db_session.exec(active_tokens_statement).all()

    # Convert to response format
    token_responses = [
        AgentTokenResponse(
            access_token=token.access_token,
            expires_at=token.expires_at
        )
        for token in active_tokens
    ]

    return AgentTokensResponse(tokens=token_responses)


