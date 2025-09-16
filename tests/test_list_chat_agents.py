"""
Feature: List agents assigned to a chat within a specific channel
  As an authenticated user, member, or agent
  I want to see all agents assigned to a chat within a channel
  So that I can understand which agents are handling the conversation

Scenario: Successfully list active agents for chat
  Given an authenticated user exists
  And a channel exists with a chat
  And multiple agents are assigned to the chat
  And the user has access to the channel
  When they request the list of agents for the chat within that channel
  Then the system returns paginated list of active agents
  And includes agent details and assignment status

Scenario: List agents with active filter
  Given an authenticated user exists
  And a channel exists with a chat
  And both active and inactive agents are assigned to the chat
  When they request the list with active=true filter
  Then the system returns only active agents

Scenario: List agents for chat that doesn't belong to specified channel
  Given an authenticated user exists
  And a channel exists
  And a chat exists but belongs to a different channel
  When they try to list agents for the chat using the wrong channel
  Then the system returns 404 Not Found error

Scenario: List agents without channel access permission
  Given an authenticated member user exists
  And a channel exists with a chat and assigned agents
  But the user doesn't have permission to access the channel
  When they try to list agents for the chat from that channel
  Then the system returns 403 Forbidden error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole, Agent
from models.channels import Channel, Chat, ChatAgent, UserChannelPermission, PlatformType
from database import get_session
from apis.chat_agents import list_chat_agents
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_list_chat_agents_success(session):
    """Test successful listing of chat agents."""

    # Given an authenticated user exists and a channel exists with a chat
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )

    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )

    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )

    session.add_all([user, channel, token])
    session.commit()
    session.refresh(user)
    session.refresh(channel)
    session.refresh(token)

    chat = Chat(
        name="Test Chat",
        channel_id=channel.id
    )

    # Create agents
    agent1 = Agent(
        name="Agent 1",
        webhook_url="https://agent1.example.com",
        is_active=True
    )

    agent2 = Agent(
        name="Agent 2",
        webhook_url="https://agent2.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([chat, agent1, agent2, token_user])
    session.commit()
    session.refresh(chat)
    session.refresh(agent1)
    session.refresh(agent2)

    # Create chat agent relationships
    chat_agent1 = ChatAgent(chat_id=chat.id, agent_id=agent1.id, active=True)
    chat_agent2 = ChatAgent(chat_id=chat.id, agent_id=agent2.id, active=True)

    session.add_all([chat_agent1, chat_agent2])
    session.commit()

    # When they request the list of agents for the chat
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    result = await list_chat_agents(
        channel_id=channel.id,
        chat_id=chat.id,
        limit=50,
        offset=0,
        active=True,  # Default behavior: only show active=True agents
        token=token,
        db_session=session
    )

    # Then the system returns paginated list of agents
    assert len(result.chat_agents) == 2
    assert result.total_count == 2
    assert result.has_more == False

    # Verify agent details
    agent_names = [ca.agent.name for ca in result.chat_agents]
    assert "Agent 1" in agent_names
    assert "Agent 2" in agent_names

    # Verify all are active
    for chat_agent in result.chat_agents:
        assert chat_agent.active == True


@pytest.mark.asyncio
async def test_list_chat_agents_with_active_filter(session):
    """Test listing agents with active filter."""

    # Given an authenticated user exists and a channel exists with a chat
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )

    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )

    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )

    session.add_all([user, channel, token])
    session.commit()
    session.refresh(user)
    session.refresh(channel)
    session.refresh(token)

    chat = Chat(
        name="Test Chat",
        channel_id=channel.id
    )

    # Create agents - one active, one inactive
    active_agent = Agent(
        name="Active Agent",
        webhook_url="https://active.example.com",
        is_active=True
    )

    inactive_agent = Agent(
        name="Inactive Agent",
        webhook_url="https://inactive.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([chat, active_agent, inactive_agent, token_user])
    session.commit()
    session.refresh(chat)
    session.refresh(active_agent)
    session.refresh(inactive_agent)

    # Create chat agent relationships - one active, one inactive
    active_chat_agent = ChatAgent(chat_id=chat.id, agent_id=active_agent.id, active=True)
    inactive_chat_agent = ChatAgent(chat_id=chat.id, agent_id=inactive_agent.id, active=False)

    session.add_all([active_chat_agent, inactive_chat_agent])
    session.commit()

    # When they request the list with default behavior (active=True)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    result = await list_chat_agents(
        channel_id=channel.id,
        chat_id=chat.id,
        limit=50,
        offset=0,
        active=True,  # Default behavior filters for active=True
        token=token,
        db_session=session
    )

    # Then the system returns only active agents
    assert len(result.chat_agents) == 1
    assert result.total_count == 1
    assert result.chat_agents[0].agent.name == "Active Agent"
    assert result.chat_agents[0].active == True

    # When they explicitly request inactive agents
    result_inactive = await list_chat_agents(
        channel_id=channel.id,
        chat_id=chat.id,
        limit=50,
        offset=0,
        active=False,  # Explicitly request inactive agents
        token=token,
        db_session=session
    )

    # Then the system returns only inactive agents
    assert len(result_inactive.chat_agents) == 1
    assert result_inactive.total_count == 1
    assert result_inactive.chat_agents[0].agent.name == "Inactive Agent"
    assert result_inactive.chat_agents[0].active == False


@pytest.mark.asyncio
async def test_list_chat_agents_wrong_channel(session):
    """Test listing agents for chat that doesn't belong to specified channel."""

    # Given an authenticated user exists and two channels with chats
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )

    channel1 = Channel(
        name="Channel 1",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1111111111"}
    )

    channel2 = Channel(
        name="Channel 2",
        platform=PlatformType.TELEGRAM,
        credentials_to_send_message={"bot_token": "bot123"}
    )

    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )

    session.add_all([user, channel1, channel2, token])
    session.commit()
    session.refresh(user)
    session.refresh(channel1)
    session.refresh(channel2)
    session.refresh(token)

    # Create chat in channel1
    chat = Chat(
        name="Test Chat",
        channel_id=channel1.id
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to list agents using the wrong channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    try:
        result = await list_chat_agents(
            channel_id=channel2.id,  # Wrong channel
            chat_id=chat.id,
            limit=50,
            offset=0,
            active=None,  # Disable active filter for this test
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_list_chat_agents_member_without_permission(session):
    """Test listing agents without channel access permission."""

    # Given an authenticated member user exists without permission to access the channel
    member = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )

    channel = Channel(
        name="Restricted Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )

    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )

    session.add_all([member, channel, token])
    session.commit()
    session.refresh(member)
    session.refresh(channel)
    session.refresh(token)

    chat = Chat(
        name="Test Chat",
        channel_id=channel.id
    )

    token_user = TokenUser(token_id=token.id, user_id=member.id)

    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to list agents from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)

    try:
        result = await list_chat_agents(
            channel_id=channel.id,
            chat_id=chat.id,
            limit=50,
            offset=0,
            active=None,  # Disable active filter for this test
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_list_chat_agents_nonexistent_chat(session):
    """Test listing agents for non-existent chat."""

    # Given an authenticated user exists and a channel exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )

    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )

    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )

    session.add_all([user, channel, token])
    session.commit()
    session.refresh(user)
    session.refresh(channel)
    session.refresh(token)

    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they try to list agents for a non-existent chat
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    try:
        result = await list_chat_agents(
            channel_id=channel.id,
            chat_id="nonexistent_chat",
            limit=50,
            offset=0,
            active=None,  # Disable active filter for this test
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()