"""
Feature: Update channel information
  As an admin user or agent
  I want to update channel information
  So that I can modify channel settings and credentials

Scenario: Admin successfully updates channel name
  Given an admin user is authenticated
  And a channel exists in the system
  When they update the channel name
  Then the system updates the channel successfully
  And returns the updated channel information

Scenario: Admin successfully updates channel credentials
  Given an admin user is authenticated
  And a channel exists in the system
  When they update the channel credentials
  Then the system updates the credentials successfully
  And returns the updated channel information without credentials

Scenario: Admin successfully updates api_to_send_message
  Given an admin user is authenticated
  And a channel exists in the system
  When they update the api_to_send_message
  Then the system updates the field successfully
  And returns the updated channel information

Scenario: Agent successfully updates channel
  Given an agent is authenticated
  And a channel exists in the system
  When they update the channel with valid data
  Then the system updates the channel successfully
  And returns the updated channel information

Scenario: Admin updates channel with partial data
  Given an admin user is authenticated
  And a channel exists in the system
  When they update only the name
  Then the system updates only the name
  And other fields remain unchanged

Scenario: Admin tries to update non-existent channel
  Given an admin user is authenticated
  When they try to update a non-existent channel
  Then the system returns 404 Not Found error

Scenario: Member user tries to update channel
  Given a member user is authenticated
  And a channel exists in the system
  When they try to update the channel
  Then the system returns 403 Forbidden error

Scenario: Unauthenticated user tries to update channel
  Given no valid authentication token is provided
  When they try to update a channel
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.channels import Channel, PlatformType
from database import get_session
from apis.channels import update_channel
from apis.schemas.channels import UpdateChannelRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_update_channel_admin_name_success(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Original Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"},
        api_to_send_message="https://api.whatsapp.com/send"
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the channel name
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateChannelRequest(name="Updated Channel Name")
    
    result = await update_channel(
        channel_id=channel.id,
        channel_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the channel successfully
    assert result.name == "Updated Channel Name"
    assert result.platform == PlatformType.WHATSAPP
    assert result.api_to_send_message == "https://api.whatsapp.com/send"
    assert result.buffer_time_seconds == 3  # Default values remain unchanged
    assert result.history_msg_count == 40
    assert result.recent_msg_window_minutes == 60*24
    assert result.id == channel.id


@pytest.mark.asyncio
async def test_update_channel_admin_credentials_success(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="WhatsApp Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890", "old_key": "old_value"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the channel credentials
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateChannelRequest(
        credentials_to_send_message={"phone": "+9876543210", "new_api_key": "secret_key"}
    )
    
    result = await update_channel(
        channel_id=channel.id,
        channel_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the credentials successfully
    assert result.name == "WhatsApp Channel"
    assert result.id == channel.id
    # And returns channel information without credentials
    assert not hasattr(result, 'credentials_to_send_message')
    
    # But stores the updated credentials in database
    channel_statement = select(Channel).where(Channel.id == result.id)
    stored_channel = session.exec(channel_statement).first()
    assert stored_channel.credentials_to_send_message == {"phone": "+9876543210", "new_api_key": "secret_key"}


@pytest.mark.asyncio
async def test_update_channel_api_to_send_message(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Telegram Channel",
        platform=PlatformType.TELEGRAM,
        credentials_to_send_message={"bot_token": "secret"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the api_to_send_message
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateChannelRequest(
        api_to_send_message="https://api.telegram.org/bot/sendMessage"
    )
    
    result = await update_channel(
        channel_id=channel.id,
        channel_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the field successfully
    assert result.api_to_send_message == "https://api.telegram.org/bot/sendMessage"
    assert result.name == "Telegram Channel"
    assert result.id == channel.id


@pytest.mark.asyncio
async def test_update_channel_buffer_time_and_counts(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Config Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+123"},
        buffer_time_seconds=3,
        history_msg_count=40,
        recent_msg_window_minutes=60*24
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the buffer time and message counts
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateChannelRequest(
        buffer_time_seconds=10,
        history_msg_count=100,
        recent_msg_window_minutes=120
    )
    
    result = await update_channel(
        channel_id=channel.id,
        channel_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the configuration fields successfully
    assert result.buffer_time_seconds == 10
    assert result.history_msg_count == 100  
    assert result.recent_msg_window_minutes == 120
    # Other fields remain unchanged
    assert result.name == "Config Channel"
    assert result.id == channel.id


@pytest.mark.asyncio
async def test_update_channel_agent_success(session):
    # Given an agent is authenticated and a channel exists
    agent = Agent(
        name="Test Agent",
        callback_url="https://agent.test/hook"
    )
    
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.INSTAGRAM,
        credentials_to_send_message={"access_token": "secret"}
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
    
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # When they update the channel with valid data
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    
    update_data = UpdateChannelRequest(
        name="Updated by Agent",
        api_to_send_message="https://graph.instagram.com/send"
    )
    
    result = await update_channel(
        channel_id=channel.id,
        channel_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the channel successfully
    assert result.name == "Updated by Agent"
    assert result.api_to_send_message == "https://graph.instagram.com/send"
    assert result.platform == PlatformType.INSTAGRAM
    assert result.id == channel.id


@pytest.mark.asyncio
async def test_update_channel_partial_data(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Original Name",
        platform=PlatformType.TELEGRAM,
        credentials_to_send_message={"bot_token": "original_token"},
        api_to_send_message="https://original-api.com"
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update only the name
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateChannelRequest(name="Partial Update")
    
    result = await update_channel(
        channel_id=channel.id,
        channel_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates only the name
    assert result.name == "Partial Update"
    # And other fields remain unchanged
    assert result.api_to_send_message == "https://original-api.com"
    
    # Verify in database
    channel_statement = select(Channel).where(Channel.id == result.id)
    stored_channel = session.exec(channel_statement).first()
    assert stored_channel.credentials_to_send_message == {"bot_token": "original_token"}


@pytest.mark.asyncio
async def test_update_channel_not_found(session):
    # Given an admin user is authenticated
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they try to update a non-existent channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateChannelRequest(name="Non-existent")
    
    try:
        result = await update_channel(
            channel_id="channel_nonexistent",
            channel_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_update_channel_member_forbidden(session):
    # Given a member user is authenticated and a channel exists
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Forbidden Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, channel, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(channel)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to update the channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    update_data = UpdateChannelRequest(name="Hacked Name")
    
    try:
        result = await update_channel(
            channel_id=channel.id,
            channel_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_update_channel_not_auth(session):
    # Given a channel exists but no valid authentication
    channel = Channel(
        name="Unauthorized Channel",
        platform=PlatformType.TELEGRAM,
        credentials_to_send_message={"bot_token": "secret"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    update_data = UpdateChannelRequest(name="Unauthorized Update")

    # When they try to update channel with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await update_channel(
            channel_id=channel.id,
            channel_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()