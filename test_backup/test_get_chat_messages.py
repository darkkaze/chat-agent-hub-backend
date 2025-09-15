"""
Feature: Get latest N messages from chat with pagination within a channel
  As an authenticated user, member, or agent
  I want to retrieve messages from a chat within a specific channel with pagination support
  So that I can view conversation history efficiently

Scenario: Successfully get recent messages without pagination
  Given an authenticated user/member/agent exists
  And a channel exists with a chat that has multiple messages
  And the user has access to the channel
  When they request messages from the chat within that channel without pagination parameters
  Then the system returns the latest 50 messages by default
  And messages are ordered by timestamp (newest first)
  And includes message content, sender_type, timestamp, and metadata

Scenario: Get messages with pagination parameters
  Given an authenticated user/member/agent exists
  And a channel exists with a chat that has many messages
  And the user has access to the channel
  When they request messages with limit=10 and offset=5 from the chat within that channel
  Then the system returns exactly 10 messages starting from the 6th most recent
  And includes pagination metadata (total_count, has_more)

Scenario: Get messages from chat that doesn't belong to specified channel
  Given an authenticated user/member/agent exists
  And a channel exists
  And a chat with messages exists but belongs to a different channel
  When they request messages from the chat using the wrong channel
  Then the system returns 404 Not Found error

Scenario: Get messages from chat with no messages
  Given an authenticated user/member/agent exists
  And a channel exists with a chat that has no messages
  And the user has access to the channel
  When they request messages from the chat within that channel
  Then the system returns an empty message list
  And pagination metadata shows total_count=0

Scenario: Get messages without channel access permission
  Given an authenticated user/member/agent exists
  And a channel exists with a chat that has messages
  But the user doesn't have permission to access the channel
  When they try to get messages from that channel
  Then the system returns 403 Forbidden error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.channels import Channel, Chat, Message, UserChannelPermission, PlatformType, SenderType
from database import get_session
from apis.chats import get_chat_messages
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_get_chat_messages_success_default_pagination(session):
    # Given an authenticated admin exists and a channel exists with a chat that has multiple messages
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
    
    chat = Chat(
        name="Test Chat",
    )
    
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Create multiple messages with different timestamps
    base_time = datetime.now(timezone.utc)
    messages = []
    for i in range(5):
        message = Message(
            chat_id=chat.id,
            content=f"Message {i+1}",
            sender_type=SenderType.CONTACT if i % 2 == 0 else SenderType.USER,
            timestamp=base_time + timedelta(minutes=i),
            meta_data={"index": i}
        )
        messages.append(message)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all(messages + [token_user])
    session.commit()

    # When they request messages from the chat within that channel without pagination parameters
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await get_chat_messages(
        chat_id=chat.id,
        limit=50,
        offset=0,
        token=token,
        db_session=session
    )

    # Then the system returns all messages
    assert len(result.messages) == 5
    assert result.total_count == 5
    assert result.has_more is False
    
    # And messages are ordered by timestamp (newest first)
    assert result.messages[0].content == "Message 5"  # Most recent
    assert result.messages[-1].content == "Message 1"  # Oldest
    
    # And includes message content, sender_type, timestamp, and metadata
    first_message = result.messages[0]
    assert first_message.content is not None
    assert first_message.sender_type is not None
    assert first_message.timestamp is not None
    assert first_message.meta_data is not None


@pytest.mark.asyncio
async def test_get_chat_messages_with_pagination(session):
    # Given an authenticated admin exists and a channel exists with a chat that has many messages
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
    
    chat = Chat(
        name="Test Chat",
    )
    
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Create 20 messages
    base_time = datetime.now(timezone.utc)
    messages = []
    for i in range(20):
        message = Message(
            chat_id=chat.id,
            content=f"Message {i+1}",
            sender_type=SenderType.CONTACT,
            timestamp=base_time + timedelta(minutes=i)
        )
        messages.append(message)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all(messages + [token_user])
    session.commit()

    # When they request messages with limit=10 and offset=5 from the chat within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await get_chat_messages(
        chat_id=chat.id,
        limit=10,
        offset=5,
        token=token,
        db_session=session
    )

    # Then the system returns exactly 10 messages starting from the 6th most recent
    assert len(result.messages) == 10
    assert result.total_count == 20
    assert result.has_more is True
    
    # Should skip the first 5 newest and return the next 10
    assert result.messages[0].content == "Message 15"  # 6th newest
    assert result.messages[-1].content == "Message 6"  # 15th newest


@pytest.mark.asyncio
async def test_get_chat_messages_wrong_channel(session):
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
    
    # Create chat with messages in channel1
    chat = Chat(
        name="Test Chat",
    )
    
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    message = Message(
        chat_id=chat.id,
        content="Hello",
        sender_type=SenderType.CONTACT
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([message, token_user])
    session.commit()

    # When they request messages from the chat using the wrong channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await get_chat_messages(
            chat_id=chat.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_get_chat_messages_empty_chat(session):
    # Given an authenticated admin exists and a channel exists with a chat that has no messages
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
    
    chat = Chat(
        name="Test Chat",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they request messages from the chat within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await get_chat_messages(
        chat_id=chat.id,
        limit=50,
        offset=0,
        token=token,
        db_session=session
    )

    # Then the system returns an empty message list and pagination metadata shows total_count=0
    assert len(result.messages) == 0
    assert result.total_count == 0
    assert result.has_more is False


@pytest.mark.asyncio
async def test_get_chat_messages_member_with_permission(session):
    # Given an authenticated member user exists with permission to access the channel
    member = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
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
    )
    
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    message = Message(
        chat_id=chat.id,
        content="Test message",
        sender_type=SenderType.CONTACT
    )
    
    token_user = TokenUser(token_id=token.id, user_id=member.id)
    
    session.add_all([message, token_user, permission])
    session.commit()

    # When they request messages from the chat
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    result = await get_chat_messages(
        chat_id=chat.id,
        limit=50,
        offset=0,
        token=token,
        db_session=session
    )

    # Then the system returns the messages
    assert len(result.messages) == 1
    assert result.messages[0].content == "Test message"


@pytest.mark.asyncio
async def test_get_chat_messages_member_without_permission(session):
    # Given an authenticated member user exists without permission to access the channel
    member = User(
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
    
    session.add_all([member, channel, token])
    session.commit()
    session.refresh(member)
    session.refresh(channel)
    session.refresh(token)
    
    chat = Chat(
        name="Test Chat",
    )
    
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    message = Message(
        chat_id=chat.id,
        content="Restricted message",
        sender_type=SenderType.CONTACT
    )
    
    token_user = TokenUser(token_id=token.id, user_id=member.id)
    
    session.add_all([message, token_user])
    session.commit()

    # When they try to get messages from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await get_chat_messages(
            chat_id=chat.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_get_chat_messages_not_auth(session):
    # Given a channel exists with a chat that has messages and no valid authentication
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
    
    message = Message(
        chat_id=chat.id,
        content="Unauthorized message",
        sender_type=SenderType.CONTACT
    )
    session.add(message)
    session.commit()

    # When they try to get messages with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await get_chat_messages(
            chat_id=chat.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()


@pytest.mark.asyncio
async def test_get_chat_messages_pagination_edge_cases(session):
    # Given an authenticated admin exists and a channel exists with a chat that has exactly 50 messages
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
    
    chat = Chat(
        name="Test Chat",
    )
    
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Create exactly 50 messages
    base_time = datetime.now(timezone.utc)
    messages = []
    for i in range(50):
        message = Message(
            chat_id=chat.id,
            content=f"Message {i+1}",
            sender_type=SenderType.CONTACT,
            timestamp=base_time + timedelta(minutes=i)
        )
        messages.append(message)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all(messages + [token_user])
    session.commit()

    # When they request messages with default pagination (limit=50, offset=0)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await get_chat_messages(
        chat_id=chat.id,
        limit=50,
        offset=0,
        token=token,
        db_session=session
    )

    # Then the system returns all 50 messages with no more available
    assert len(result.messages) == 50
    assert result.total_count == 50
    assert result.has_more is False
    
    # And messages are ordered by timestamp (newest first)
    assert result.messages[0].content == "Message 50"  # Most recent
    assert result.messages[-1].content == "Message 1"  # Oldest
    
    # When they request with limit=25, offset=0
    result_page1 = await get_chat_messages(
        chat_id=chat.id,
        limit=25,
        offset=0,
        token=token,
        db_session=session
    )
    
    # Then the system returns first 25 messages with more available
    assert len(result_page1.messages) == 25
    assert result_page1.total_count == 50
    assert result_page1.has_more is True
    assert result_page1.messages[0].content == "Message 50"  # Most recent
    assert result_page1.messages[-1].content == "Message 26"  # 25th newest
    
    # When they request with limit=25, offset=25
    result_page2 = await get_chat_messages(
        chat_id=chat.id,
        limit=25,
        offset=25,
        token=token,
        db_session=session
    )
    
    # Then the system returns last 25 messages with no more available
    assert len(result_page2.messages) == 25
    assert result_page2.total_count == 50
    assert result_page2.has_more is False
    assert result_page2.messages[0].content == "Message 25"  # 26th newest
    assert result_page2.messages[-1].content == "Message 1"  # Oldest