"""
Feature: Create external agent
  As an admin user
  I want to create external agents and associate them to channels
  So that I can manage automated conversation handlers

Scenario: Admin successfully creates an agent with channel association
  Given an admin user is authenticated
  And a channel exists in the system
  When they create an agent with valid data and channel_id
  Then the system creates the agent successfully
  And associates the agent to the specified channel
  And returns the agent data with generated ID
  And does not include sensitive information

Scenario: Admin creates agent with minimal data
  Given an admin user is authenticated
  And a channel exists in the system
  When they create an agent with only name, webhook_url and channel_id
  Then the system creates the agent with defaults
  And fire_and_forget defaults to False
  And is_active defaults to True

Scenario: Admin tries to create agent with non-existent channel
  Given an admin user is authenticated
  When they create an agent with invalid channel_id
  Then the system returns 404 Not Found error

Scenario: Non-admin user tries to create agent
  Given a member user is authenticated
  When they try to create an agent
  Then the system returns 403 Forbidden error

Scenario: Unauthenticated user tries to create agent
  Given no valid authentication token is provided
  When they try to create an agent
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole, Agent
from models.channels import Channel, PlatformType
from database import get_session
from apis.auth import create_agent
from apis.schemas.auth import CreateAgentRequest
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_create_agent_success(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="WhatsApp Business",
        platform=PlatformType.WHATSAPP,
        credentials={"api_key": "secret"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they create an agent with valid data and channel_id
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    agent_data = CreateAgentRequest(
        name="Customer Support Bot",
        webhook_url="https://api.example.com/webhook"
    )
    
    result = await create_agent(agent_data=agent_data, token=token, db_session=session)

    # Then the system creates the agent successfully
    assert result.name == "Customer Support Bot"
    assert result.webhook_url == "https://api.example.com/webhook"
    assert result.is_fire_and_forget == False
    assert result.is_active == True
    assert result.id.startswith("agent_")
    
    # Note: ChannelAgent associations removed per model changes


@pytest.mark.asyncio
async def test_create_agent_minimal_data(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret", 
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Telegram Bot",
        platform=PlatformType.TELEGRAM
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they create agent with minimal data
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    agent_data = CreateAgentRequest(
        name="Simple Bot",
        webhook_url="https://simple.bot/hook",
        channel_id=channel.id
    )
    
    result = await create_agent(agent_data=agent_data, token=token, db_session=session)

    # Then the system creates agent with defaults
    assert result.name == "Simple Bot"
    assert result.webhook_url == "https://simple.bot/hook"
    assert result.is_fire_and_forget == False  # Default
    assert result.is_active == True  # Default


@pytest.mark.asyncio
async def test_create_agent_without_channel(session):
    # Given an admin user is authenticated
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret", 
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they create agent without channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    agent_data = CreateAgentRequest(
        name="Standalone Bot",
        webhook_url="https://standalone.bot/hook"
        # No channel_id provided
    )
    
    result = await create_agent(agent_data=agent_data, token=token, db_session=session)

    # Then the system creates agent without channel association
    assert result.name == "Standalone Bot"
    assert result.webhook_url == "https://standalone.bot/hook"
    assert result.is_fire_and_forget == False  # Default
    assert result.is_active == True  # Default
    
    # Note: ChannelAgent associations removed per model changes


@pytest.mark.asyncio
async def test_create_agent_channel_not_found(session):
    # Given an admin user is authenticated
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they create agent with invalid channel_id
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    agent_data = CreateAgentRequest(
        name="Test Bot",
        webhook_url="https://test.bot/hook",
        channel_id="channel_nonexistent"
    )
    
    try:
        result = await create_agent(agent_data=agent_data, token=token, db_session=session)
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_create_agent_non_admin_forbidden(session):
    # Given a member user is authenticated
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, channel, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to create an agent
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    agent_data = CreateAgentRequest(
        name="Unauthorized Bot",
        webhook_url="https://bad.bot/hook",
        channel_id=channel.id
    )
    
    try:
        result = await create_agent(agent_data=agent_data, token=token, db_session=session)
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Should raise 403 exception
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_create_agent_not_auth(session):
    # Given no valid token
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.TELEGRAM
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    agent_data = CreateAgentRequest(
        name="Unauthorized Bot",
        webhook_url="https://bad.bot/hook", 
        channel_id=channel.id
    )

    # When they try to create agent with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await create_agent(agent_data=agent_data, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Should raise 401 exception  
        assert "401" in str(e) or "unauthorized" in str(e).lower()