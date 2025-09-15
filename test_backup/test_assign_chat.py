"""
Feature: Assign chat to a team user within a specific channel
  As an authenticated user, member, or agent
  I want to assign a chat to a specific team user within a channel
  So that conversations can be properly managed and handled

Scenario: Successfully assign chat to user
  Given an authenticated user/member/agent exists
  And a channel exists with an unassigned chat
  And the user has access to the channel
  And a team user exists
  When they assign the chat to the team user within that channel
  Then the system updates the chat's assigned_user_id
  And returns success confirmation with updated chat details

Scenario: Reassign already assigned chat
  Given an authenticated user/member/agent exists
  And a channel exists with a chat assigned to user A
  And the user has access to the channel
  And another team user B exists
  When they reassign the chat to user B within that channel
  Then the system updates the chat's assigned_user_id to user B
  And returns success confirmation

Scenario: Assign chat that doesn't belong to specified channel
  Given an authenticated user/member/agent exists
  And a channel exists
  And a chat exists but belongs to a different channel
  When they try to assign the chat from the wrong channel
  Then the system returns 404 Not Found error

Scenario: Assign chat to non-existent user
  Given an authenticated user/member/agent exists
  And a channel exists with a chat
  And the user has access to the channel
  When they try to assign the chat to a non-existent user
  Then the system returns 404 Not Found error

Scenario: Assign chat without channel access permission
  Given an authenticated user/member/agent exists
  And a channel exists with a chat
  But the user doesn't have permission to access the channel
  When they try to assign the chat from that channel
  Then the system returns 403 Forbidden error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.channels import Channel, Chat, UserChannelPermission, PlatformType
from database import get_session
from apis.chats import assign_chat
from apis.schemas.chats import AssignChatRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_assign_chat_success(session):
    # Given an authenticated admin exists and a channel with an unassigned chat and a team user exists
    admin = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    team_user = User(
        username="team_user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin, team_user, channel, token])
    session.commit()
    session.refresh(admin)
    session.refresh(team_user)
    session.refresh(channel)
    session.refresh(token)
    
    # Create unassigned chat
    chat = Chat(
        name="Test Chat",
        channel_id=channel.id,
        # No assigned_user_id - unassigned
    )
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they assign the chat to the team user within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    assign_data = AssignChatRequest(user_id=team_user.id)
    
    result = await assign_chat(
        channel_id=channel.id,
        chat_id=chat.id,
        assign_data=assign_data,
        token=token,
        db_session=session
    )

    # Then the system updates the chat's assigned_user_id
    assert result.assigned_user_id == team_user.id
    assert result.id == chat.id
    assert result.channel_id == channel.id
    
    # Verify in database
    chat_statement = select(Chat).where(Chat.id == chat.id)
    stored_chat = session.exec(chat_statement).first()
    assert stored_chat.assigned_user_id == team_user.id


@pytest.mark.asyncio
async def test_reassign_chat(session):
    # Given an authenticated admin exists and a channel with a chat assigned to user A and another user B exists
    admin = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    user_a = User(
        username="user_a",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    user_b = User(
        username="user_b",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin, user_a, user_b, channel, token])
    session.commit()
    session.refresh(admin)
    session.refresh(user_a)
    session.refresh(user_b)
    session.refresh(channel)
    session.refresh(token)
    
    # Create chat assigned to user_a
    chat = Chat(
        name="Test Chat",
        channel_id=channel.id,
        assigned_user_id=user_a.id
    )
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they reassign the chat to user B within that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    assign_data = AssignChatRequest(user_id=user_b.id)
    
    result = await assign_chat(
        channel_id=channel.id,
        chat_id=chat.id,
        assign_data=assign_data,
        token=token,
        db_session=session
    )

    # Then the system updates the chat's assigned_user_id to user B
    assert result.assigned_user_id == user_b.id
    assert result.id == chat.id
    
    # Verify in database
    chat_statement = select(Chat).where(Chat.id == chat.id)
    stored_chat = session.exec(chat_statement).first()
    assert stored_chat.assigned_user_id == user_b.id


@pytest.mark.asyncio
async def test_assign_chat_wrong_channel(session):
    # Given an authenticated admin exists and two channels with chats
    admin = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    team_user = User(
        username="team_user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
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
    
    session.add_all([admin, team_user, channel1, channel2, token])
    session.commit()
    session.refresh(admin)
    session.refresh(team_user)
    session.refresh(channel1)
    session.refresh(channel2)
    session.refresh(token)
    
    # Create chat in channel1
    chat = Chat(
        name="Test Chat",
        channel_id=channel1.id
    )
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to assign the chat from the wrong channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    assign_data = AssignChatRequest(user_id=team_user.id)
    
    try:
        result = await assign_chat(
            channel_id=channel2.id,
            chat_id=chat.id,
            assign_data=assign_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_assign_chat_nonexistent_user(session):
    # Given an authenticated admin exists and a channel exists with a chat
    admin = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin, channel, token])
    session.commit()
    session.refresh(admin)
    session.refresh(channel)
    session.refresh(token)
    
    chat = Chat(
        name="Test Chat",
        channel_id=channel.id
    )
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all([chat, token_user])
    session.commit()
    session.refresh(chat)

    # When they try to assign the chat to a non-existent user
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    assign_data = AssignChatRequest(user_id="nonexistent_user")
    
    try:
        result = await assign_chat(
            channel_id=channel.id,
            chat_id=chat.id,
            assign_data=assign_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_assign_chat_member_with_permission(session):
    # Given an authenticated member user exists with permission to access the channel
    member = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    team_user = User(
        username="team_user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member, team_user, channel, token])
    session.commit()
    session.refresh(member)
    session.refresh(team_user)
    session.refresh(channel)
    session.refresh(token)
    
    chat = Chat(
        name="Test Chat",
        channel_id=channel.id
    )
    
    token_user = TokenUser(token_id=token.id, user_id=member.id)
    
    # Give member permission to access the channel
    permission = UserChannelPermission(
        user_id=member.id,
        channel_id=channel.id
    )
    
    session.add_all([chat, token_user, permission])
    session.commit()
    session.refresh(chat)

    # When they assign the chat to the team user
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    assign_data = AssignChatRequest(user_id=team_user.id)
    
    result = await assign_chat(
        channel_id=channel.id,
        chat_id=chat.id,
        assign_data=assign_data,
        token=token,
        db_session=session
    )

    # Then the system updates the chat's assigned_user_id
    assert result.assigned_user_id == team_user.id


@pytest.mark.asyncio
async def test_assign_chat_member_without_permission(session):
    # Given an authenticated member user exists without permission to access the channel
    member = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    team_user = User(
        username="team_user",
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
    
    session.add_all([member, team_user, channel, token])
    session.commit()
    session.refresh(member)
    session.refresh(team_user)
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

    # When they try to assign the chat from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    assign_data = AssignChatRequest(user_id=team_user.id)
    
    try:
        result = await assign_chat(
            channel_id=channel.id,
            chat_id=chat.id,
            assign_data=assign_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_assign_chat_not_auth(session):
    # Given a channel exists with a chat and no valid authentication
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    team_user = User(
        username="team_user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    session.add_all([channel, team_user])
    session.commit()
    session.refresh(channel)
    session.refresh(team_user)
    
    chat = Chat(
        name="Test Chat",
        channel_id=channel.id
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)

    # When they try to assign the chat with invalid token
    from helpers.auth import get_auth_token
    assign_data = AssignChatRequest(user_id=team_user.id)
    
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await assign_chat(
            channel_id=channel.id,
            chat_id=chat.id,
            assign_data=assign_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()