"""
Feature: Get specific chat details within a channel
  As an authenticated user, member, or agent
  I want to get detailed information about a specific chat within a channel
  So that I can view conversation context and metadata

Scenario: Successfully get chat details
  Given an authenticated user/member/agent exists
  And a channel exists with a specific chat
  And the user has access to the channel
  When they request details for the specific chat within that channel
  Then the system returns complete chat information
  And includes associated channel information
  And includes assigned user information if applicable

Scenario: Get chat that doesn't belong to specified channel
  Given an authenticated user/member/agent exists
  And a channel exists
  And a chat exists but belongs to a different channel
  When they request the chat details from the wrong channel
  Then the system returns 404 Not Found error

Scenario: Get details for non-existent chat within channel
  Given an authenticated user/member/agent exists
  And a channel exists
  And the user has access to the channel
  When they request details for a non-existent chat within that channel
  Then the system returns 404 Not Found error

Scenario: Get chat details without channel access permission
  Given an authenticated member user exists
  And a channel exists with a chat
  But the user doesn't have permission to access the channel
  When they try to get chat details from that channel
  Then the system returns 403 Forbidden error

Scenario: Get chat details without authentication
  Given a channel exists with a chat
  And no valid authentication token is provided
  When they try to get chat details
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.channels import Channel, Chat, UserChannelPermission, PlatformType
from database import get_session
from apis.chats import get_chat
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_get_chat_success(session):
    # Given an authenticated admin exists and a channel exists with a specific chat
    user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    assigned_user = User(
        username="assigned_user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, assigned_user, channel, token])
    session.commit()
    session.refresh(user)
    session.refresh(assigned_user)
    session.refresh(channel)
    session.refresh(token)
    
    # Create chat with metadata
    chat = Chat(
        name="Test Chat",
        external_id="ext_123",
        assigned_user_id=assigned_user.id,
        meta_data={"contact_name": "John Doe", "phone": "+1234567890"}
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they request details for the specific chat within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await get_chat(
        chat_id=chat.id,
        token=token,
        db_session=session
    )

    # Then the system returns complete chat information
    assert result.id == chat.id
    assert result.name == "Test Chat"
    assert result.external_id == "ext_123"
    assert result.channel_id == channel.id
    assert result.assigned_user_id == assigned_user.id
    assert result.meta_data["contact_name"] == "John Doe"


@pytest.mark.asyncio
async def test_get_chat_wrong_channel(session):
    # Given an authenticated admin exists and two channels with chats
    user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel1 = Channel(
        name="Channel 1",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1111111111"}
    )
    
    channel2 = Channel(
        name="Channel 2", 
        platform=PlatformType.TELEGRAM,
        credentials={"bot_token": "bot123"}
    )
    
    token = Token(
        access_token="admin_token",
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
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they request the chat details from the wrong channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await get_chat(
            chat_id=chat.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_get_chat_nonexistent_chat(session):
    # Given an authenticated admin exists and a channel exists
    user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="admin_token",
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

    # When they request details for a non-existent chat within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await get_chat(
            chat_id="nonexistent_chat",
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_get_chat_member_without_permission(session):
    # Given an authenticated member user exists without permission to access the channel
    user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Restricted Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="member_token",
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
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to get chat details from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await get_chat(
            chat_id=chat.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_get_chat_member_with_permission(session):
    # Given an authenticated member user exists with permission to access the channel
    user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Accessible Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="member_token",
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
        external_id="ext_456",
        meta_data={"source": "website"}
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user, permission])
    session.commit()
    session.refresh(chat)

    # When they request chat details from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    result = await get_chat(
        chat_id=chat.id,
        token=token,
        db_session=session
    )

    # Then the system returns complete chat information
    assert result.id == chat.id
    assert result.external_id == "ext_456"
    assert result.channel_id == channel.id
    assert result.meta_data["source"] == "website"


@pytest.mark.asyncio
async def test_get_chat_not_auth(session):
    # Given a channel exists with a chat and no valid authentication
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
    )
    
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    chat = Chat(
        name="Test Chat",
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)

    # When they try to get chat details with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await get_chat(
            chat_id=chat.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()