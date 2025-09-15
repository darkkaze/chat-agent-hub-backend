"""
Feature: Get channel details
  As an authenticated user or agent
  I want to retrieve details of a specific channel
  So that I can see channel information

Scenario: Admin successfully gets any channel details
  Given an admin user is authenticated
  And a channel exists in the system
  When they request channel details with GET /channels/{channel_id}
  Then the system returns the channel information
  And includes id, name, platform
  And does not include sensitive credential information

Scenario: Member gets accessible channel details
  Given a member user is authenticated
  And a channel exists that the member has permission to access
  When they request channel details with GET /channels/{channel_id}
  Then the system returns the channel information
  And does not include credentials

Scenario: Member tries to get restricted channel details
  Given a member user is authenticated
  And a channel exists but the member has no permission to access it
  When they request channel details with GET /channels/{channel_id}
  Then the system returns 403 Forbidden error

Scenario: Agent gets any channel details
  Given an agent is authenticated
  And a channel exists in the system
  When they request channel details with GET /channels/{channel_id}
  Then the system returns the channel information
  And does not include credentials

Scenario: Get non-existent channel
  Given a valid authentication token exists
  When they request details for a non-existent channel
  Then the system returns 404 Not Found error

Scenario: Get channel without authentication
  Given no valid authentication token is provided
  When they request channel details with GET /channels/{channel_id}
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.channels import Channel, UserChannelPermission, PlatformType
from database import get_session
from apis.channels import get_channel
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_get_channel_admin_success(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="WhatsApp Business",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890", "api_key": "secret_key"}
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
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they request channel details
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)

    result = await get_channel(channel_id=channel.id, token=token, db_session=session)

    # Then the system returns the channel information
    assert result.id == channel.id
    assert result.name == "WhatsApp Business"
    assert result.platform == PlatformType.WHATSAPP
    # And does not include credentials
    assert not hasattr(result, 'credentials')


@pytest.mark.asyncio
async def test_get_channel_member_with_permission_success(session):
    # Given a member user is authenticated with permission to a channel
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Telegram Bot",
        platform=PlatformType.TELEGRAM,
        credentials_to_send_message={"bot_token": "secret_token"}
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
    
    # Link token to member user
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()
    
    # Give member permission to the channel
    permission = UserChannelPermission(
        user_id=member_user.id,
        channel_id=channel.id
    )
    session.add(permission)
    session.commit()

    # When they request channel details
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)

    result = await get_channel(channel_id=channel.id, token=token, db_session=session)

    # Then the system returns the channel information
    assert result.id == channel.id
    assert result.name == "Telegram Bot"
    assert result.platform == PlatformType.TELEGRAM
    assert not hasattr(result, 'credentials')


@pytest.mark.asyncio
async def test_get_channel_member_no_permission_forbidden(session):
    # Given a member user is authenticated but has no permission to a channel
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Restricted Channel",
        platform=PlatformType.INSTAGRAM,
        credentials_to_send_message={"access_token": "secret"}
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

    # When they try to get channel details without permission
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await get_channel(channel_id=channel.id, token=token, db_session=session)
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower() or "no permission" in str(e).lower()


@pytest.mark.asyncio
async def test_get_channel_agent_success(session):
    # Given an agent is authenticated and a channel exists
    agent = Agent(
        name="Channel Reader Agent",
        webhook_url="https://agent.example.com/callback"
    )
    
    channel = Channel(
        name="Instagram Direct",
        platform=PlatformType.INSTAGRAM,
        credentials_to_send_message={"access_token": "secret_token", "page_id": "123456"}
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
    
    # Link token to agent
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # When they request channel details
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)

    result = await get_channel(channel_id=channel.id, token=token, db_session=session)

    # Then the system returns the channel information
    assert result.id == channel.id
    assert result.name == "Instagram Direct"
    assert result.platform == PlatformType.INSTAGRAM
    assert not hasattr(result, 'credentials')


@pytest.mark.asyncio
async def test_get_channel_not_found(session):
    # Given a valid admin token but non-existent channel
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

    # When they request details for non-existent channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await get_channel(channel_id="nonexistent_channel", token=token, db_session=session)
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_get_channel_not_auth(session):
    # Given a channel exists but invalid token
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)

    # When they request channel details with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()