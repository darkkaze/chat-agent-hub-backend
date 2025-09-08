"""
Feature: List chats within a specific channel
  As an authenticated user, member, or agent
  I want to get a list of chats from a specific channel
  So that I can see conversations within that channel

Scenario: Successfully list all chats in a channel
  Given an authenticated user/member/agent exists
  And a channel exists with multiple chats
  And the user has access to the channel
  When they request chats from the specific channel
  Then the system returns all chats from that channel
  And includes basic chat information (id, contact_id, assigned_user_id, meta_data)

Scenario: Filter chats by assigned user within channel
  Given an authenticated user/member/agent exists
  And a channel exists with chats assigned to different users
  And the user has access to the channel
  When they request chats filtered by assigned_user_id
  Then the system returns only chats from that channel assigned to that user

Scenario: Filter chats by assignment status within channel
  Given an authenticated user/member/agent exists
  And a channel exists with both assigned and unassigned chats
  And the user has access to the channel
  When they request chats filtered by assignment status
  Then the system returns chats from that channel matching the assignment status

Scenario: List chats from channel without access permission
  Given an authenticated member user exists
  And a channel exists with chats
  But the user doesn't have permission to access the channel
  When they request chats from that channel
  Then the system returns 403 Forbidden error

Scenario: List chats from non-existent channel
  Given an authenticated user/member/agent exists
  When they request chats from a non-existent channel
  Then the system returns 404 Not Found error

Scenario: List chats without authentication
  Given a channel exists with chats
  And no valid authentication token is provided
  When they try to list chats from the channel
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.channels import Channel, Chat, UserChannelPermission, PlatformType
from database import get_session
from apis.chats import list_chats
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_list_chats_success_admin(session):
    # Given an authenticated admin exists and a channel exists with multiple chats
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
    
    # Create chats in the channel
    chat1 = Chat(
        external_id="ext_1",
        channel_id=channel.id,
        contact_id="contact_1"
    )
    chat2 = Chat(
        external_id="ext_2", 
        channel_id=channel.id,
        contact_id="contact_2",
        assigned_user_id=user.id
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat1, chat2, token_user])
    session.commit()

    # When they request chats from the specific channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await list_chats(
        channel_id=channel.id,
        limit=50,
        offset=0,
        assigned_user_id=None,
        assigned=None,
        token=token,
        db_session=session
    )

    # Then the system returns all chats from that channel
    assert len(result.chats) == 2
    assert result.total_count == 2
    assert result.has_more is False
    assert result.chats[0].channel_id == channel.id
    assert result.chats[1].channel_id == channel.id


@pytest.mark.asyncio
async def test_list_chats_filter_by_assigned_user(session):
    # Given an authenticated admin exists and a channel with chats assigned to different users
    admin = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    user1 = User(
        username="user1",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    user2 = User(
        username="user2", 
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
    
    session.add_all([admin, user1, user2, channel, token])
    session.commit()
    session.refresh(admin)
    session.refresh(user1)
    session.refresh(user2)
    session.refresh(channel)
    session.refresh(token)
    
    # Create chats assigned to different users
    chat1 = Chat(
        channel_id=channel.id,
        contact_id="contact_1",
        assigned_user_id=user1.id
    )
    chat2 = Chat(
        channel_id=channel.id,
        contact_id="contact_2",
        assigned_user_id=user2.id
    )
    chat3 = Chat(
        channel_id=channel.id,
        contact_id="contact_3",
        assigned_user_id=user1.id
    )
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all([chat1, chat2, chat3, token_user])
    session.commit()

    # When they request chats filtered by assigned_user_id
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await list_chats(
        channel_id=channel.id,
        limit=50,
        offset=0,
        assigned_user_id=user1.id,
        assigned=None,
        token=token,
        db_session=session
    )

    # Then the system returns only chats assigned to that user
    assert len(result.chats) == 2
    assert result.total_count == 2
    assert result.has_more is False
    assert all(chat.assigned_user_id == user1.id for chat in result.chats)


@pytest.mark.asyncio
async def test_list_chats_filter_by_assignment_status(session):
    # Given an authenticated admin exists and a channel with both assigned and unassigned chats
    admin = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    user1 = User(
        username="user1",
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
    
    session.add_all([admin, user1, channel, token])
    session.commit()
    session.refresh(admin)
    session.refresh(user1)
    session.refresh(channel)
    session.refresh(token)
    
    # Create both assigned and unassigned chats
    chat1 = Chat(
        channel_id=channel.id,
        contact_id="contact_1",
        assigned_user_id=user1.id
    )
    chat2 = Chat(
        channel_id=channel.id,
        contact_id="contact_2"
        # No assigned_user_id - unassigned
    )
    chat3 = Chat(
        channel_id=channel.id,
        contact_id="contact_3"
        # No assigned_user_id - unassigned  
    )
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all([chat1, chat2, chat3, token_user])
    session.commit()

    # When they request chats filtered by unassigned status
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await list_chats(
        channel_id=channel.id,
        limit=50,
        offset=0,
        assigned_user_id=None,
        assigned=False,
        token=token,
        db_session=session
    )

    # Then the system returns unassigned chats only
    assert len(result.chats) == 2
    assert result.total_count == 2
    assert result.has_more is False
    assert all(chat.assigned_user_id is None for chat in result.chats)


@pytest.mark.asyncio
async def test_list_chats_member_without_permission(session):
    # Given an authenticated member user exists but doesn't have permission to access the channel
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
        channel_id=channel.id,
        contact_id="contact_1"
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([chat, token_user])
    session.commit()

    # When they request chats from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await list_chats(
            channel_id=channel.id,
            limit=50,
            offset=0,
            assigned_user_id=None,
            assigned=None,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_list_chats_member_with_permission(session):
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
        channel_id=channel.id,
        contact_id="contact_1"
    )
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    permission = UserChannelPermission(user_id=user.id, channel_id=channel.id)
    
    session.add_all([chat, token_user, permission])
    session.commit()

    # When they request chats from that channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    result = await list_chats(
        channel_id=channel.id,
        limit=50,
        offset=0,
        assigned_user_id=None,
        assigned=None,
        token=token,
        db_session=session
    )

    # Then the system returns chats from that channel
    assert len(result.chats) == 1
    assert result.total_count == 1
    assert result.has_more is False
    assert result.chats[0].channel_id == channel.id


@pytest.mark.asyncio
async def test_list_chats_nonexistent_channel(session):
    # Given an authenticated user exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="user_token",
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

    # When they request chats from a non-existent channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await list_chats(
            channel_id="nonexistent_channel",
            limit=50,
            offset=0,
            assigned_user_id=None,
            assigned=None,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_list_chats_not_auth(session):
    # Given a channel exists with chats and no valid authentication
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
    )
    
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    chat = Chat(
        channel_id=channel.id,
        contact_id="contact_1"
    )
    session.add(chat)
    session.commit()

    # When they try to list chats with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await list_chats(
            channel_id=channel.id,
            limit=50,
            offset=0,
            assigned_user_id=None,
            assigned=None,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()


@pytest.mark.asyncio
async def test_list_chats_ordered_by_last_message_ts(session):
    # Given an authenticated admin exists and a channel exists with chats with different last_message_ts
    admin = User(
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
    
    session.add_all([admin, channel, token])
    session.commit()
    session.refresh(admin)
    session.refresh(channel)
    session.refresh(token)
    
    # Create chats with specific last_message_ts timestamps
    old_time = datetime.now(timezone.utc) - timedelta(hours=3)
    recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
    newest_time = datetime.now(timezone.utc)
    
    chat_old = Chat(
        channel_id=channel.id,
        contact_id="contact_old",
        last_message_ts=old_time
    )
    chat_recent = Chat(
        channel_id=channel.id,
        contact_id="contact_recent", 
        last_message_ts=recent_time
    )
    chat_newest = Chat(
        channel_id=channel.id,
        contact_id="contact_newest",
        last_message_ts=newest_time
    )
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all([chat_old, chat_recent, chat_newest, token_user])
    session.commit()

    # When they request chats from the channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await list_chats(
        channel_id=channel.id,
        limit=50,
        offset=0,
        assigned_user_id=None,
        assigned=None,
        token=token,
        db_session=session
    )

    # Then the system returns chats ordered by last_message_ts descending (newest first)
    assert len(result.chats) == 3
    assert result.chats[0].contact_id == "contact_newest"
    assert result.chats[1].contact_id == "contact_recent"
    assert result.chats[2].contact_id == "contact_old"
    
    # Verify timestamps are in descending order
    assert result.chats[0].last_message_ts >= result.chats[1].last_message_ts
    assert result.chats[1].last_message_ts >= result.chats[2].last_message_ts


@pytest.mark.asyncio
async def test_list_chats_pagination(session):
    # Given an authenticated admin exists and a channel exists with many chats
    admin = User(
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
    
    session.add_all([admin, channel, token])
    session.commit()
    session.refresh(admin)
    session.refresh(channel)
    session.refresh(token)
    
    # Create 25 chats
    chats = []
    for i in range(25):
        chat = Chat(
            channel_id=channel.id,
            contact_id=f"contact_{i+1}"
        )
        chats.append(chat)
    
    token_user = TokenUser(token_id=token.id, user_id=admin.id)
    
    session.add_all(chats + [token_user])
    session.commit()

    # When they request first page with limit=10
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await list_chats(
        channel_id=channel.id,
        limit=10,
        offset=0,
        assigned_user_id=None,
        assigned=None,
        token=token,
        db_session=session
    )

    # Then the system returns first 10 chats with pagination metadata
    assert len(result.chats) == 10
    assert result.total_count == 25
    assert result.has_more is True
    
    # When they request second page with limit=10 and offset=10
    result_page2 = await list_chats(
        channel_id=channel.id,
        limit=10,
        offset=10,
        assigned_user_id=None,
        assigned=None,
        token=token,
        db_session=session
    )
    
    # Then the system returns next 10 chats
    assert len(result_page2.chats) == 10
    assert result_page2.total_count == 25
    assert result_page2.has_more is True
    
    # When they request third page with limit=10 and offset=20
    result_page3 = await list_chats(
        channel_id=channel.id,
        limit=10,
        offset=20,
        assigned_user_id=None,
        assigned=None,
        token=token,
        db_session=session
    )
    
    # Then the system returns last 5 chats
    assert len(result_page3.chats) == 5
    assert result_page3.total_count == 25
    assert result_page3.has_more is False