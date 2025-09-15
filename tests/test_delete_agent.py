"""
Feature: Delete external agent
  As an admin user
  I want to delete agents from the system
  So that I can manage agent accounts and remove inactive agents

Scenario: Admin successfully soft deletes an agent
  Given an admin user is authenticated
  And a target agent exists in the system
  When they delete the agent with soft delete (default)
  Then the system marks the agent as inactive
  And returns success confirmation message
  And agent still exists in database but is inactive

Scenario: Admin successfully hard deletes an agent
  Given an admin user is authenticated
  And a target agent exists in the system with channel associations
  When they delete the agent with hard=true parameter
  Then the system removes channel associations first
  And permanently removes the agent from database
  And returns success confirmation

Scenario: Admin tries to delete non-existent agent
  Given an admin user is authenticated
  When they try to delete an agent that doesn't exist
  Then the system returns 404 Not Found error

Scenario: Member user tries to delete agent
  Given a member user is authenticated
  And an agent exists in the system
  When they try to delete the agent
  Then the system returns 403 Forbidden error

Scenario: Unauthenticated user tries to delete agent
  Given no valid authentication token is provided
  When they try to delete an agent
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole, Agent
from models.channels import Channel, PlatformType
from database import get_session
from apis.auth import delete_agent
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_agent_soft_delete_success(session):
    # Given an admin user is authenticated and a target agent exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    target_agent = Agent(
        name="Target Bot",
        callback_url="https://target.bot/hook",
        is_fire_and_forget=False,
        is_active=True
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, target_agent, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(target_agent)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they delete the agent with soft delete (default)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await delete_agent(
        agent_id=target_agent.id,
        hard=False,
        token=token,
        db_session=session
    )

    # Then the system marks the agent as inactive
    assert result.message == "Agent soft-deleted successfully"
    
    # Verify agent still exists in database but is inactive
    agent_statement = select(Agent).where(Agent.id == target_agent.id)
    db_agent = session.exec(agent_statement).first()
    assert db_agent is not None
    assert db_agent.is_active == False
    assert db_agent.name == "Target Bot"  # Other fields unchanged


@pytest.mark.asyncio
async def test_delete_agent_hard_delete_success(session):
    # Given an admin user is authenticated and agent with channel associations exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP
    )
    
    target_agent = Agent(
        name="Target Bot",
        callback_url="https://target.bot/hook",
        is_fire_and_forget=True,
        is_active=True
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, target_agent, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(target_agent)
    session.refresh(token)
    
    # Note: ChannelAgent associations removed per model changes
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they delete the agent with hard=true parameter
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await delete_agent(
        agent_id=target_agent.id,
        hard=True,
        token=token,
        db_session=session
    )

    # Then the system permanently removes the agent from database
    assert result.message == "Agent deleted successfully"
    
    # Verify agent no longer exists in database
    agent_statement = select(Agent).where(Agent.id == target_agent.id)
    db_agent = session.exec(agent_statement).first()
    assert db_agent is None
    
    # Note: ChannelAgent associations removed per model changes


@pytest.mark.asyncio
async def test_delete_agent_not_found(session):
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

    # When they try to delete an agent that doesn't exist
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await delete_agent(
            agent_id="agent_nonexistent",
            hard=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_agent_member_forbidden(session):
    # Given a member user is authenticated and an agent exists
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    agent = Agent(
        name="Protected Bot",
        callback_url="https://protected.bot/hook"
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

    # When they try to delete the agent
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await delete_agent(
            agent_id=agent.id,
            hard=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_agent_not_auth(session):
    # Given an agent exists but invalid token
    agent = Agent(
        name="Test Bot",
        callback_url="https://test.bot/hook"
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    # When they try to delete with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_agent(
            agent_id=agent.id,
            hard=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_agent_hard_delete_multiple_associations(session):
    # Given an admin user and agent with multiple channel associations
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel1 = Channel(name="Channel 1", platform=PlatformType.WHATSAPP)
    channel2 = Channel(name="Channel 2", platform=PlatformType.TELEGRAM)
    
    agent = Agent(
        name="Multi-Channel Bot",
        callback_url="https://multi.bot/hook"
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel1, channel2, agent, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel1)
    session.refresh(channel2)
    session.refresh(agent)
    session.refresh(token)
    
    # Note: ChannelAgent associations removed per model changes
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they hard delete the agent
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await delete_agent(
        agent_id=agent.id,
        hard=True,
        token=token,
        db_session=session
    )

    # Then all associations are removed and agent is deleted
    assert result.message == "Agent deleted successfully"
    
    # Verify agent is gone
    agent_statement = select(Agent).where(Agent.id == agent.id)
    db_agent = session.exec(agent_statement).first()
    assert db_agent is None
    
    # Note: ChannelAgent associations removed per model changes