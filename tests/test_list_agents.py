"""
Feature: List external agents
  As an authenticated user or agent
  I want to retrieve a list of system agents
  So that I can see agent information

Scenario: Successfully list active agents with valid token
  Given a valid authentication token exists
  And there are agents in the system with different statuses
  When they request the agent list with GET /agents
  Then the system returns only active agents by default
  And each agent includes id, name, callback_url, is_fire_and_forget, is_active
  And does not include sensitive information

Scenario: Successfully list inactive agents when explicitly requested
  Given a valid authentication token exists
  And there are inactive agents in the system
  When they request the agent list with GET /agents?is_active=false
  Then the system returns only inactive agents
  And does not include sensitive information

Scenario: List agents without authentication
  Given no valid authentication token is provided
  When they request the agent list with GET /agents
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole, Agent
from database import get_session
from apis.auth import list_agents
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_list_agents_success(session):
    # Given a valid token and agents with different statuses
    active_agent1 = Agent(
        name="Active Bot 1",
        webhook_url="https://active1.bot/hook",
        is_fire_and_forget=False,
        is_active=True
    )
    
    active_agent2 = Agent(
        name="Active Bot 2", 
        webhook_url="https://active2.bot/hook",
        is_fire_and_forget=True,
        is_active=True
    )
    
    inactive_agent = Agent(
        name="Inactive Bot",
        webhook_url="https://inactive.bot/hook",
        is_fire_and_forget=False,
        is_active=False
    )
    
    token = Token(
        access_token="valid_jwt_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([active_agent1, active_agent2, inactive_agent, token])
    session.commit()

    # When they request agent list (default is_active=True)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer valid_jwt_token", db_session=session)
    result = await list_agents(is_active=True, token=token, db_session=session)

    # Then the system returns only active agents
    assert len(result) == 2
    agent_names = [agent.name for agent in result]
    assert "Active Bot 1" in agent_names
    assert "Active Bot 2" in agent_names
    assert "Inactive Bot" not in agent_names
    
    # And includes all expected fields
    for agent in result:
        assert hasattr(agent, 'id')
        assert hasattr(agent, 'name') 
        assert hasattr(agent, 'webhook_url')
        assert hasattr(agent, 'is_fire_and_forget')
        assert hasattr(agent, 'is_active')
        assert agent.is_active == True


@pytest.mark.asyncio
async def test_list_agents_inactive(session):
    # Given agents with different statuses
    active_agent = Agent(
        name="Active Bot",
        webhook_url="https://active.bot/hook",
        is_active=True
    )
    
    inactive_agent1 = Agent(
        name="Inactive Bot 1",
        webhook_url="https://inactive1.bot/hook", 
        is_active=False
    )
    
    inactive_agent2 = Agent(
        name="Inactive Bot 2",
        webhook_url="https://inactive2.bot/hook",
        is_active=False
    )
    
    token = Token(
        access_token="valid_jwt_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([active_agent, inactive_agent1, inactive_agent2, token])
    session.commit()

    # When they request inactive agents explicitly
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer valid_jwt_token", db_session=session)
    result = await list_agents(is_active=False, token=token, db_session=session)

    # Then the system returns only inactive agents
    assert len(result) == 2
    agent_names = [agent.name for agent in result]
    assert "Inactive Bot 1" in agent_names
    assert "Inactive Bot 2" in agent_names
    assert "Active Bot" not in agent_names
    
    for agent in result:
        assert agent.is_active == False


@pytest.mark.asyncio
async def test_list_agents_empty_list(session):
    # Given no agents exist but valid token
    token = Token(
        access_token="valid_jwt_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add(token)
    session.commit()

    # When they request agent list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer valid_jwt_token", db_session=session)
    result = await list_agents(is_active=True, token=token, db_session=session)

    # Then the system returns empty list
    assert len(result) == 0
    assert isinstance(result, list)


@pytest.mark.asyncio 
async def test_list_agents_not_auth(session):
    # Given agents exist but invalid token
    agent = Agent(
        name="Test Bot",
        webhook_url="https://test.bot/hook"
    )
    session.add(agent)
    session.commit()

    # When they request agent list with invalid token
    from helpers.auth import get_auth_token
    try:
        # This should fail at token validation
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await list_agents(is_active=True, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Should raise 401 exception
        assert "401" in str(e) or "unauthorized" in str(e).lower()