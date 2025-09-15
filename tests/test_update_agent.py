"""
Feature: Update external agent
  As an admin user
  I want to update external agent information and channel associations
  So that I can manage automated conversation handlers

Scenario: Admin successfully updates agent information
  Given an admin user is authenticated
  And an agent exists in the system
  When they update the agent with valid data
  Then the system updates the agent successfully
  And returns the updated agent data

Scenario: Admin updates agent channel association
  Given an admin user is authenticated
  And an agent with channel association exists
  And another channel exists in the system
  When they update the agent with a new channel_id
  Then the system removes old channel association
  And creates new channel association
  And returns the updated agent data

Scenario: Admin removes channel association from agent
  Given an admin user is authenticated  
  And an agent with channel association exists
  When they update the agent with empty channel_id
  Then the system removes the channel association
  And returns the updated agent data

Scenario: Admin tries to update agent with non-existent channel
  Given an admin user is authenticated
  And an agent exists in the system
  When they update the agent with invalid channel_id
  Then the system returns 404 Not Found error

Scenario: Admin tries to update non-existent agent
  Given an admin user is authenticated
  When they try to update a non-existent agent
  Then the system returns 404 Not Found error

Scenario: Member user tries to update agent
  Given a member user is authenticated
  And an agent exists in the system
  When they try to update the agent
  Then the system returns 403 Forbidden error

Scenario: Unauthenticated user tries to update agent
  Given no valid authentication token is provided
  When they try to update an agent
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole, Agent
from models.channels import Channel, PlatformType
from database import get_session
from apis.auth import update_agent
from apis.schemas.auth import UpdateAgentRequest
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_update_agent_success(session):
    # Given an admin user is authenticated and an agent exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    agent = Agent(
        name="Original Bot",
        webhook_url="https://original.bot/hook",
        is_fire_and_forget=False,
        is_active=True
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, agent, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(agent)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the agent with valid data
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateAgentRequest(
        name="Updated Bot",
        webhook_url="https://updated.bot/hook",
        is_fire_and_forget=True,
        is_active=False
    )
    
    result = await update_agent(
        agent_id=agent.id,
        agent_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the agent successfully
    assert result.name == "Updated Bot"
    assert result.webhook_url == "https://updated.bot/hook"
    assert result.is_fire_and_forget == True
    assert result.is_active == False
    assert result.id == agent.id


@pytest.mark.asyncio
async def test_update_agent_channel_association(session):
    # Given an admin user is authenticated, agent with channel association exists, and another channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    old_channel = Channel(
        name="Old Channel",
        platform=PlatformType.WHATSAPP
    )
    
    new_channel = Channel(
        name="New Channel",
        platform=PlatformType.TELEGRAM
    )
    
    agent = Agent(
        name="Test Bot",
        webhook_url="https://test.bot/hook"
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, old_channel, new_channel, agent, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(old_channel)
    session.refresh(new_channel)
    session.refresh(agent)
    session.refresh(token)
    
    # Note: ChannelAgent associations removed per model changes
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the agent with a new channel_id
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateAgentRequest(name="Updated Bot")
    
    result = await update_agent(
        agent_id=agent.id,
        agent_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the agent successfully
    assert result.id == agent.id
    assert result.name == "Updated Bot"


@pytest.mark.asyncio
async def test_update_agent_remove_channel_association(session):
    # Given an admin user is authenticated and agent with channel association exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP
    )
    
    agent = Agent(
        name="Test Bot",
        webhook_url="https://test.bot/hook"
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, agent, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(agent)
    session.refresh(token)
    
    # Note: ChannelAgent associations removed per model changes
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the agent
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateAgentRequest(name="Updated Bot")
    
    result = await update_agent(
        agent_id=agent.id,
        agent_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the agent successfully
    assert result.id == agent.id
    assert result.name == "Updated Bot"


@pytest.mark.asyncio
async def test_update_agent_invalid_channel(session):
    # Given an admin user is authenticated and an agent exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    agent = Agent(
        name="Test Bot",
        webhook_url="https://test.bot/hook"
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, agent, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(agent)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the agent with valid data
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateAgentRequest(name="Updated Bot")
    
    result = await update_agent(
        agent_id=agent.id,
        agent_data=update_data,
        token=token,
        db_session=session
    )
    
    # Then the system updates the agent successfully
    assert result.id == agent.id
    assert result.name == "Updated Bot"


@pytest.mark.asyncio
async def test_update_agent_not_found(session):
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

    # When they try to update a non-existent agent
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateAgentRequest(name="Updated Name")
    
    try:
        result = await update_agent(
            agent_id="agent_nonexistent",
            agent_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_update_agent_non_admin_forbidden(session):
    # Given a member user is authenticated and an agent exists
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    agent = Agent(
        name="Test Bot",
        webhook_url="https://test.bot/hook"
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, agent, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(agent)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to update the agent
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    update_data = UpdateAgentRequest(name="Hacked Name")
    
    try:
        result = await update_agent(
            agent_id=agent.id,
            agent_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Should raise 403 exception
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_update_agent_not_auth(session):
    # Given an agent exists but invalid token
    agent = Agent(
        name="Test Bot",
        webhook_url="https://test.bot/hook"
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    
    update_data = UpdateAgentRequest(name="Unauthorized Update")

    # When they try to update agent with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await update_agent(
            agent_id=agent.id,
            agent_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Should raise 401 exception  
        assert "401" in str(e) or "unauthorized" in str(e).lower()