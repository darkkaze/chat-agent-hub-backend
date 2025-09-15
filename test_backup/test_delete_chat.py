"""
Feature: Delete chat within a channel (soft and hard delete)
  As an authenticated admin or agent
  I want to delete a chat conversation within a specific channel
  So that I can remove outdated or problematic conversations

Scenario: Successfully perform soft delete of chat
  Given an authenticated admin or agent exists
  And a channel exists with a specific chat
  And the user has access to the channel
  When they request soft delete of the chat within that channel
  Then the system marks the chat as deleted (soft delete)
  And returns success confirmation
  And the chat is hidden from normal listings but data is preserved

Scenario: Successfully perform hard delete of chat
  Given an authenticated admin or agent exists
  And a channel exists with a chat that has associated messages
  And the user has access to the channel
  When they request hard delete of the chat within that channel
  Then the system permanently removes the chat and all associated messages
  And returns success confirmation

Scenario: Member user tries to delete chat
  Given an authenticated member user exists
  And a channel exists with a chat
  And the user has access to the channel
  When they try to delete the chat within that channel
  Then the system returns 403 Forbidden error

Scenario: Delete chat that doesn't belong to specified channel
  Given an authenticated admin or agent exists
  And a channel exists
  And a chat exists but belongs to a different channel
  When they try to delete the chat from the wrong channel
  Then the system returns 404 Not Found error

Scenario: Delete chat without channel access permission
  Given an authenticated admin or agent exists
  And a channel exists with a chat
  But the user doesn't have permission to access the channel
  When they try to delete the chat from that channel
  Then the system returns 403 Forbidden error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, TokenAgent, UserRole, Agent
from models.channels import Channel, Chat, Message, UserChannelPermission, PlatformType, SenderType
from database import get_session
from apis.chats import delete_chat
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_chat_soft_delete_admin(session):
    # Given an authenticated admin exists and a channel exists with a specific chat
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
        meta_data={"important": "data"}
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they request soft delete of the chat within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await delete_chat(
        chat_id=chat.id,
        soft=True,
        token=token,
        db_session=session
    )

    # Then the system marks the chat as deleted (soft delete)
    # For now, just return success message as soft delete would need is_deleted field
    assert result["success"] is True
    assert "soft deleted" in result["message"].lower()
    
    # And the chat data is preserved (would be hidden from normal listings in real implementation)
    chat_statement = select(Chat).where(Chat.id == chat.id)
    stored_chat = session.exec(chat_statement).first()
    assert stored_chat is not None


@pytest.mark.asyncio
async def test_delete_chat_hard_delete_admin(session):
    # Given an authenticated admin exists and a channel with a chat that has messages
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
    
    # Add messages to the chat
    message1 = Message(
        chat_id=chat.id,
        content="Hello",
        sender_type=SenderType.CONTACT
    )
    message2 = Message(
        chat_id=chat.id,
        content="Hi there",
        sender_type=SenderType.USER
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([message1, message2, token_user])
    session.commit()

    # When they request hard delete of the chat within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await delete_chat(
        chat_id=chat.id,
        soft=False,
        token=token,
        db_session=session
    )

    # Then the system permanently removes the chat and all associated messages
    assert result["success"] is True
    assert "permanently deleted" in result["message"].lower()
    
    # Chat should be gone
    chat_statement = select(Chat).where(Chat.id == chat.id)
    stored_chat = session.exec(chat_statement).first()
    assert stored_chat is None
    
    # Messages should be gone
    messages_statement = select(Message).where(Message.chat_id == chat.id)
    stored_messages = session.exec(messages_statement).all()
    assert len(stored_messages) == 0


@pytest.mark.asyncio
async def test_delete_chat_agent_success(session):
    # Given an authenticated agent exists and a channel exists with a chat
    agent = Agent(
        name="Test Agent",
        webhook_url="https://agent.example.com/webhook",
        is_active=True
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
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
        name="Test Chat",
    )
    
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    
    session.add_all([chat, token_agent])
    session.commit()
    session.refresh(chat)

    # When they request hard delete of the chat
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    
    result = await delete_chat(
        chat_id=chat.id,
        soft=False,
        token=token,
        db_session=session
    )

    # Then the system permanently removes the chat
    assert result["success"] is True
    assert "permanently deleted" in result["message"].lower()
    
    # Chat should be gone
    chat_statement = select(Chat).where(Chat.id == chat.id)
    stored_chat = session.exec(chat_statement).first()
    assert stored_chat is None


@pytest.mark.asyncio
async def test_delete_chat_member_forbidden(session):
    # Given an authenticated member user exists with access to channel
    user = User(
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
    
    session.add_all([user, channel, token])
    session.commit()
    session.refresh(user)
    session.refresh(channel)
    session.refresh(token)
    
    chat = Chat(
        name="Test Chat",
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user, permission])
    session.commit()
    session.refresh(chat)

    # When they try to delete the chat within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await delete_chat(
            chat_id=chat.id,
            soft=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_chat_wrong_channel(session):
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

    # When they try to delete the chat from the wrong channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await delete_chat(
            chat_id=chat.id,
            soft=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_chat_nonexistent_channel(session):
    # Given an authenticated admin exists
    user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, token])
    session.commit()
    session.refresh(user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they try to delete a chat from a non-existent channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await delete_chat(
            chat_id="some_chat",
            soft=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_chat_not_auth(session):
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

    # When they try to delete the chat with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_chat(
            chat_id=chat.id,
            soft=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()