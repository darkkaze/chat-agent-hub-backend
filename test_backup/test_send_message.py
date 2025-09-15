"""
Feature: Send message to chat within a specific channel
  As an authenticated user, member, or agent
  I want to send a message to a chat conversation within a channel
  So that I can communicate within the conversation

Scenario: Successfully send message as user
  Given an authenticated user exists
  And a channel exists with a chat
  And the user has access to the channel
  When they send a message with content to the chat within that channel
  Then the system creates a new message with sender_type=USER
  And stores the message with current timestamp
  And returns the created message details

Scenario: Successfully send message as agent
  Given an authenticated agent exists
  And a channel exists with a chat
  When they send a message with content to the chat within that channel
  Then the system creates a new message with sender_type=AGENT
  And stores the message with current timestamp
  And returns the created message details

Scenario: Send message with metadata
  Given an authenticated user/agent exists
  And a channel exists with a chat
  And the user has access to the channel
  When they send a message with content and additional metadata to the chat within that channel
  Then the system stores the message with the provided metadata
  And returns the complete message details including metadata

Scenario: Send message to chat that doesn't belong to specified channel
  Given an authenticated user/member/agent exists
  And a channel exists
  And a chat exists but belongs to a different channel
  When they try to send a message to the chat using the wrong channel
  Then the system returns 404 Not Found error

Scenario: Send message without channel access permission
  Given an authenticated user/member/agent exists
  And a channel exists with a chat
  But the user doesn't have permission to access the channel
  When they try to send a message to the chat from that channel
  Then the system returns 403 Forbidden error

Scenario: Send empty message
  Given an authenticated user/member/agent exists
  And a channel exists with a chat
  And the user has access to the channel
  When they try to send a message with empty content to the chat within that channel
  Then the system returns 400 Bad Request error
"""

import pytest
from unittest.mock import AsyncMock, patch
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, TokenAgent, UserRole, Agent
from models.channels import Channel, Chat, Message, UserChannelPermission, PlatformType, SenderType
from database import get_session
from apis.chats import send_message
from apis.schemas.chats import SendMessageRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_send_message_as_user(session):
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
        name="Chat with Contact 1",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # Mock the MessageSender to avoid external API calls
    with patch('outbound.message_sender.MessageSender.send_to_platform', new_callable=AsyncMock) as mock_sender:
        # When they send a message with content to the chat within that channel
        from helpers.auth import get_auth_token
        token = await get_auth_token(authorization="Bearer user_token", db_session=session)
        
        message_data = SendMessageRequest(
            content="Hello from user!",
            meta_data={"source": "web"}
        )
        
        result = await send_message(
            chat_id=chat.id,
            message_data=message_data,
            token=token,
            db_session=session
        )

        # Then the system creates a new message with sender_type=USER
        assert result.sender_type == SenderType.USER
        assert result.content == "Hello from user!"
        assert result.chat_id == chat.id
        assert result.meta_data["source"] == "web"
        assert result.timestamp is not None
        assert result.id is not None
        
        # And the message sender was called
        mock_sender.assert_called_once()
        
        # Verify in database
        message_statement = select(Message).where(Message.id == result.id)
        stored_message = session.exec(message_statement).first()
        assert stored_message is not None
        assert stored_message.sender_type == SenderType.USER


@pytest.mark.asyncio
async def test_send_message_as_agent(session):
    # Given an authenticated agent exists and a channel exists with a chat
    agent = Agent(
        name="Test Agent",
        webhook_url="https://agent.example.com/webhook",
        is_active=True
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="agent_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([agent, channel, token])
    session.commit()
    session.refresh(agent)
    session.refresh(channel)
    session.refresh(token)
    
    chat = Chat(
        name="Chat with Contact 1",
    )
    
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    
    session.add_all([chat, token_agent])
    session.commit()
    session.refresh(chat)

    # Mock the MessageSender to avoid external API calls
    with patch('outbound.message_sender.MessageSender.send_to_platform', new_callable=AsyncMock) as mock_sender:
        # When they send a message with content to the chat within that channel
        from helpers.auth import get_auth_token
        token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
        
        message_data = SendMessageRequest(
            content="Hello from agent!",
            meta_data={"agent_version": "1.0"}
        )
        
        result = await send_message(
            chat_id=chat.id,
            message_data=message_data,
            token=token,
            db_session=session
        )

        # Then the system creates a new message with sender_type=AGENT
        assert result.sender_type == SenderType.AGENT
        assert result.content == "Hello from agent!"
        assert result.chat_id == chat.id
        assert result.meta_data["agent_version"] == "1.0"
        assert result.timestamp is not None
        
        # And the message sender was called
        mock_sender.assert_called_once()
        
        # Verify in database
        message_statement = select(Message).where(Message.id == result.id)
        stored_message = session.exec(message_statement).first()
        assert stored_message is not None
        assert stored_message.sender_type == SenderType.AGENT


@pytest.mark.asyncio
async def test_send_message_with_metadata(session):
    # Given an authenticated user exists and a channel exists with a chat
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
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
        name="Chat with Contact 1",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user, permission])
    session.commit()
    session.refresh(chat)

    # When they send a message with content and additional metadata
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    message_data = SendMessageRequest(
        content="Message with rich metadata",
        meta_data={
            "priority": "high",
            "category": "support",
            "attachments": ["file1.pdf", "image2.jpg"]
        }
    )
    
    result = await send_message(
        chat_id=chat.id,
        message_data=message_data,
        token=token,
        db_session=session
    )

    # Then the system stores the message with the provided metadata
    assert result.content == "Message with rich metadata"
    assert result.meta_data["priority"] == "high"
    assert result.meta_data["category"] == "support"
    assert result.meta_data["attachments"] == ["file1.pdf", "image2.jpg"]
    
    # Verify in database
    message_statement = select(Message).where(Message.id == result.id)
    stored_message = session.exec(message_statement).first()
    assert stored_message.meta_data["priority"] == "high"


@pytest.mark.asyncio
async def test_send_message_wrong_channel(session):
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
        name="Chat in Channel 1",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to send a message to the chat using the wrong channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    message_data = SendMessageRequest(content="Wrong channel message")
    
    try:
        result = await send_message(
            chat_id=chat.id,
            message_data=message_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_send_message_member_without_permission(session):
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
        name="Chat with Contact 1",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=member.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to send a message to the chat from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    message_data = SendMessageRequest(content="Unauthorized message")
    
    try:
        result = await send_message(
            chat_id=chat.id,
            message_data=message_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_send_message_nonexistent_chat(session):
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

    # When they try to send a message to a non-existent chat
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    message_data = SendMessageRequest(content="Message to nowhere")
    
    try:
        result = await send_message(
            chat_id="nonexistent_chat",
            message_data=message_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_send_empty_message(session):
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
        name="Chat with Contact 1",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to send a message with empty content (this should be caught by Pydantic validation)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        message_data = SendMessageRequest(content="")  # Empty content
        result = await send_message(
            chat_id=chat.id,
            message_data=message_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a validation error"
    except Exception as e:
        # Then the system returns 400 Bad Request error (Pydantic validation)
        assert "validation" in str(e).lower() or "400" in str(e) or "bad request" in str(e).lower()


@pytest.mark.asyncio
async def test_send_message_not_auth(session):
    # Given a channel exists with a chat and no valid authentication
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    chat = Chat(
        name="Chat with Contact 1",
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)

    # When they try to send a message with invalid token
    from helpers.auth import get_auth_token
    message_data = SendMessageRequest(content="Unauthorized message")
    
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await send_message(
            chat_id=chat.id,
            message_data=message_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()


@pytest.mark.asyncio
async def test_send_message_updates_last_message_ts(session):
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
        name="Chat with Contact 1",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)
    
    # Store initial last_message_ts
    initial_last_message_ts = chat.last_message_ts

    # Mock the MessageSender to avoid external API calls
    with patch('outbound.message_sender.MessageSender.send_to_platform', new_callable=AsyncMock) as mock_sender:
        # When they send a message to the chat
        from helpers.auth import get_auth_token
        token = await get_auth_token(authorization="Bearer user_token", db_session=session)
        
        message_data = SendMessageRequest(
            content="Hello, this should update last_message_ts!",
            meta_data={"test": "value"}
        )
        
        result = await send_message(
            chat_id=chat.id,
            message_data=message_data,
            token=token,
            db_session=session
        )

        # Then the chat's last_message_ts, last_sender_type, and last_message should be updated
        session.refresh(chat)
        assert chat.last_message_ts == result.timestamp
        assert chat.last_message_ts > initial_last_message_ts
        assert chat.last_sender_type == SenderType.USER
        assert chat.last_message == "Hello, this should update last_message_ts!"
        
        # And the message sender was called
        mock_sender.assert_called_once()
        
        # Verify in database
        chat_statement = select(Chat).where(Chat.id == chat.id)
        updated_chat = session.exec(chat_statement).first()
        assert updated_chat.last_message_ts == result.timestamp
        assert updated_chat.last_sender_type == SenderType.USER
        assert updated_chat.last_message == "Hello, this should update last_message_ts!"