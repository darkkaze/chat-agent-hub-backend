"""
Feature: List channels user has access to
  As an authenticated user or agent
  I want to retrieve channels I have access to
  So that I can see available communication channels

Scenario: Admin successfully lists all channels
  Given an admin user is authenticated
  And there are channels in the system with different platforms
  When they request the channel list with GET /channels
  Then the system returns all channels in the system
  And each channel includes id, name, platform
  And does not include sensitive credential information

Scenario: Member lists only accessible channels
  Given a member user is authenticated
  And there are multiple channels in the system
  And the member has permission to access some channels but not others
  When they request the channel list with GET /channels
  Then the system returns only channels they have permission to access
  And does not include channels without permission

Scenario: Member with no channel permissions
  Given a member user is authenticated
  And there are channels in the system
  But the member has no UserChannelPermission records
  When they request the channel list with GET /channels
  Then the system returns an empty list

Scenario: Agent successfully lists all channels
  Given an agent is authenticated
  And there are channels in the system with different platforms
  When they request the channel list with GET /channels
  Then the system returns all channels in the system
  And each channel includes id, name, platform

Scenario: List channels without authentication
  Given no valid authentication token is provided
  When they request the channel list with GET /channels
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.channels import Channel, UserChannelPermission, PlatformType
from database import get_session
from apis.channels import list_channels
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_list_channels_admin_success(session):
    # Given an admin user is authenticated and channels exist
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel1 = Channel(
        name="WhatsApp Business",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890", "api_key": "secret"},
        api_to_send_message="https://api.whatsapp.com/send"
    )
    
    channel2 = Channel(
        name="Telegram Bot",
        platform=PlatformType.TELEGRAM,
        credentials_to_send_message={"bot_token": "secret_token"},
        api_to_send_message="https://api.telegram.org/bot/sendMessage"
    )
    
    channel3 = Channel(
        name="Instagram Direct",
        platform=PlatformType.INSTAGRAM,
        credentials_to_send_message={"access_token": "secret_access"}
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel1, channel2, channel3, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel1)
    session.refresh(channel2)
    session.refresh(channel3)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they request the channel list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    result = await list_channels(token=token, db_session=session)

    # Then the system returns all channels
    assert len(result) == 3
    channel_names = [channel.name for channel in result]
    assert "WhatsApp Business" in channel_names
    assert "Telegram Bot" in channel_names
    assert "Instagram Direct" in channel_names
    
    # And each channel includes id, name, platform but not credentials
    for channel in result:
        assert hasattr(channel, 'id')
        assert hasattr(channel, 'name')
        assert hasattr(channel, 'platform')
        assert not hasattr(channel, 'credentials')


@pytest.mark.asyncio
async def test_list_channels_member_with_permissions(session):
    # Given a member user is authenticated with permissions to some channels
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    accessible_channel = Channel(
        name="Accessible Channel",
        platform=PlatformType.WHATSAPP
    )
    
    restricted_channel = Channel(
        name="Restricted Channel",
        platform=PlatformType.TELEGRAM
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, accessible_channel, restricted_channel, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(accessible_channel)
    session.refresh(restricted_channel)
    session.refresh(token)
    
    # Link token to member user
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()
    
    # Give member permission to accessible channel only
    permission = UserChannelPermission(
        user_id=member_user.id,
        channel_id=accessible_channel.id
    )
    session.add(permission)
    session.commit()

    # When they request the channel list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    result = await list_channels(token=token, db_session=session)

    # Then the system returns only accessible channels
    assert len(result) == 1
    assert result[0].name == "Accessible Channel"
    assert result[0].platform == PlatformType.WHATSAPP


@pytest.mark.asyncio
async def test_list_channels_member_no_permissions(session):
    # Given a member user with no channel permissions
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Some Channel",
        platform=PlatformType.WHATSAPP
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, channel, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they request the channel list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    result = await list_channels(token=token, db_session=session)

    # Then the system returns an empty list
    assert len(result) == 0
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_channels_agent_success(session):
    # Given an agent is authenticated and channels exist
    agent = Agent(
        name="Chat Agent",
        callback_url="https://agent.example.com/callback"
    )
    
    channel1 = Channel(
        name="WhatsApp Channel",
        platform=PlatformType.WHATSAPP
    )
    
    channel2 = Channel(
        name="Telegram Channel",
        platform=PlatformType.TELEGRAM
    )
    
    token = Token(
        access_token="agent_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([agent, channel1, channel2, token])
    session.commit()
    session.refresh(agent)
    session.refresh(channel1)
    session.refresh(channel2)
    session.refresh(token)
    
    # Link token to agent
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # When they request the channel list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    result = await list_channels(token=token, db_session=session)

    # Then the system returns all channels
    assert len(result) == 2
    channel_names = [channel.name for channel in result]
    assert "WhatsApp Channel" in channel_names
    assert "Telegram Channel" in channel_names


@pytest.mark.asyncio
async def test_list_channels_not_auth(session):
    # Given channels exist but invalid token
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP
    )
    session.add(channel)
    session.commit()

    # When they request channel list with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await list_channels(token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()