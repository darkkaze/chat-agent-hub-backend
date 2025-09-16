"""
Feature: Update agent assignment for a chat within a specific channel
  As an authenticated user, member, or agent
  I want to update the active status of an agent assigned to a chat
  So that I can enable or disable specific agents for conversations

Scenario: Successfully update chat agent active status
  Given an authenticated user exists
  And a channel exists with a chat
  And an agent is assigned to the chat with active=True
  And the user has access to the channel
  When they update the agent's active status to False within that channel
  Then the system updates the agent assignment status
  And returns the updated agent details

Scenario: Update agent from inactive to active
  Given an authenticated user exists
  And a channel exists with a chat
  And an agent is assigned to the chat with active=False
  When they update the agent's active status to True
  Then the system enables the agent for the chat

Scenario: Update agent for chat that doesn't belong to specified channel
  Given an authenticated user exists
  And a channel exists
  And a chat exists but belongs to a different channel with an assigned agent
  When they try to update the agent using the wrong channel
  Then the system returns 404 Not Found error

Scenario: Update non-existent agent assignment
  Given an authenticated user exists
  And a channel exists with a chat
  And an agent exists but is not assigned to the chat
  When they try to update the agent assignment
  Then the system returns 404 Not Found error

Scenario: Update agent without channel access permission
  Given an authenticated member user exists
  And a channel exists with a chat and assigned agent
  But the user doesn't have permission to access the channel
  When they try to update the agent assignment from that channel
  Then the system returns 403 Forbidden error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole, Agent
from models.channels import Channel, Chat, ChatAgent, UserChannelPermission, PlatformType
from database import get_session
from apis.chat_agents import update_chat_agent
from apis.schemas.chat_agents import UpdateChatAgentRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_update_chat_agent_success(session):
    """Test successful update of chat agent active status."""

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

    # Create agent
    agent = Agent(
        name="Test Agent",
        webhook_url="https://agent.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([chat, agent, token_user])
    session.commit()
    session.refresh(chat)
    session.refresh(agent)

    # Create chat agent relationship with active=True
    chat_agent = ChatAgent(chat_id=chat.id, agent_id=agent.id, active=True)

    session.add(chat_agent)
    session.commit()
    session.refresh(chat_agent)

    # When they update the agent's active status to False
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    update_request = UpdateChatAgentRequest(active=False)

    result = await update_chat_agent(
        channel_id=channel.id,
        chat_id=chat.id,
        agent_id=agent.id,
        update_data=update_request,
        token=token,
        db_session=session
    )

    # Then the system updates the agent assignment status
    assert result.id == chat_agent.id
    assert result.chat_id == chat.id
    assert result.agent_id == agent.id
    assert result.active == False

    # Verify agent details are still present
    assert result.agent.name == "Test Agent"
    assert result.agent.webhook_url == "https://agent.example.com"

    # Verify in database
    session.refresh(chat_agent)
    assert chat_agent.active == False


@pytest.mark.asyncio
async def test_update_chat_agent_inactive_to_active(session):
    """Test updating agent from inactive to active."""

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

    agent = Agent(
        name="Test Agent",
        webhook_url="https://agent.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([chat, agent, token_user])
    session.commit()
    session.refresh(chat)
    session.refresh(agent)

    # Create chat agent relationship with active=False
    chat_agent = ChatAgent(chat_id=chat.id, agent_id=agent.id, active=False)

    session.add(chat_agent)
    session.commit()
    session.refresh(chat_agent)

    # When they update the agent's active status to True
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    update_request = UpdateChatAgentRequest(active=True)

    result = await update_chat_agent(
        channel_id=channel.id,
        chat_id=chat.id,
        agent_id=agent.id,
        update_data=update_request,
        token=token,
        db_session=session
    )

    # Then the system enables the agent for the chat
    assert result.active == True

    # Verify in database
    session.refresh(chat_agent)
    assert chat_agent.active == True


@pytest.mark.asyncio
async def test_update_chat_agent_wrong_channel(session):
    """Test updating chat agent for chat that doesn't belong to specified channel."""

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

    # Create chat in channel1 with agent
    chat = Chat(
        name="Test Chat",
        channel_id=channel1.id
    )

    agent = Agent(
        name="Test Agent",
        webhook_url="https://agent.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([chat, agent, token_user])
    session.commit()
    session.refresh(chat)
    session.refresh(agent)

    chat_agent = ChatAgent(chat_id=chat.id, agent_id=agent.id, active=True)
    session.add(chat_agent)
    session.commit()

    # When they try to update the agent using the wrong channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    update_request = UpdateChatAgentRequest(active=False)

    try:
        result = await update_chat_agent(
            channel_id=channel2.id,  # Wrong channel
            chat_id=chat.id,
            agent_id=agent.id,
            update_data=update_request,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_update_chat_agent_not_assigned(session):
    """Test updating non-existent agent assignment."""

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

    # Create agent but don't assign to chat
    agent = Agent(
        name="Unassigned Agent",
        webhook_url="https://agent.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([chat, agent, token_user])
    session.commit()
    session.refresh(chat)
    session.refresh(agent)

    # When they try to update the agent assignment
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    update_request = UpdateChatAgentRequest(active=False)

    try:
        result = await update_chat_agent(
            channel_id=channel.id,
            chat_id=chat.id,
            agent_id=agent.id,
            update_data=update_request,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()
        assert "Agent not assigned to this chat" in str(e)


@pytest.mark.asyncio
async def test_update_chat_agent_member_without_permission(session):
    """Test updating chat agent without channel access permission."""

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

    agent = Agent(
        name="Test Agent",
        webhook_url="https://agent.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=member.id)

    session.add_all([chat, agent, token_user])
    session.commit()
    session.refresh(chat)
    session.refresh(agent)

    chat_agent = ChatAgent(chat_id=chat.id, agent_id=agent.id, active=True)
    session.add(chat_agent)
    session.commit()

    # When they try to update the agent assignment from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)

    update_request = UpdateChatAgentRequest(active=False)

    try:
        result = await update_chat_agent(
            channel_id=channel.id,
            chat_id=chat.id,
            agent_id=agent.id,
            update_data=update_request,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_update_chat_agent_nonexistent_chat(session):
    """Test updating agent for non-existent chat."""

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

    agent = Agent(
        name="Test Agent",
        webhook_url="https://agent.example.com",
        is_active=True
    )

    token_user = TokenUser(token_id=token.id, user_id=user.id)

    session.add_all([agent, token_user])
    session.commit()
    session.refresh(agent)

    # When they try to update agent for a non-existent chat
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)

    update_request = UpdateChatAgentRequest(active=False)

    try:
        result = await update_chat_agent(
            channel_id=channel.id,
            chat_id="nonexistent_chat",
            agent_id=agent.id,
            update_data=update_request,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()