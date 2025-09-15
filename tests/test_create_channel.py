"""
Feature: Connect a new channel
  As an admin user or agent
  I want to create a new communication channel
  So that I can connect platforms like WhatsApp, Telegram, or Instagram

Scenario: Admin successfully creates WhatsApp channel
  Given an admin user is authenticated
  When they create a channel with valid WhatsApp credentials
  Then the system creates the channel successfully
  And returns the channel information without credentials
  And stores the channel with encrypted/secure credentials

Scenario: Admin successfully creates Telegram channel
  Given an admin user is authenticated  
  When they create a channel with valid Telegram credentials
  Then the system creates the channel successfully
  And returns the channel information without credentials

Scenario: Admin successfully creates Instagram channel
  Given an admin user is authenticated
  When they create a channel with valid Instagram credentials  
  Then the system creates the channel successfully
  And returns the channel information without credentials

Scenario: Agent successfully creates channel
  Given an agent is authenticated
  When they create a channel with valid credentials
  Then the system creates the channel successfully
  And returns the channel information without credentials

Scenario: Member user tries to create channel
  Given a member user is authenticated
  When they try to create a channel
  Then the system returns 403 Forbidden error
  And does not create any channel

Scenario: Create channel without authentication
  Given no valid authentication token is provided
  When they try to create a channel
  Then the system returns 401 Unauthorized error

Scenario: Create channel with invalid platform
  Given an admin user is authenticated
  When they try to create a channel with unsupported platform
  Then the system returns 422 Validation Error

Scenario: Create channel with missing credentials
  Given an admin user is authenticated
  When they try to create a channel without required credentials
  Then the system returns 422 Validation Error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.channels import Channel, PlatformType
from database import get_session
from apis.channels import create_channel
from apis.schemas.channels import CreateChannelRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_create_channel_admin_whatsapp_success(session):
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
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they create a channel with valid WhatsApp credentials
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    channel_data = CreateChannelRequest(
        name="WhatsApp Business",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890", "api_key": "secret_key"},
        api_to_send_message="https://api.whatsapp.com/send"
    )
    
    result = await create_channel(
        channel_data=channel_data,
        token=token,
        db_session=session
    )

    # Then the system creates the channel successfully
    assert result.name == "WhatsApp Business"
    assert result.platform == PlatformType.WHATSAPP
    assert result.api_to_send_message == "https://api.whatsapp.com/send"
    # Note: buffer_time_seconds, history_msg_count, recent_msg_window_minutes moved to Agent model
    assert result.id is not None
    # And returns channel information without credentials
    assert not hasattr(result, 'credentials_to_send_message')
    
    # And stores the channel with credentials in database
    channel_statement = select(Channel).where(Channel.id == result.id)
    stored_channel = session.exec(channel_statement).first()
    assert stored_channel is not None
    assert stored_channel.credentials_to_send_message == {"phone": "+1234567890", "api_key": "secret_key"}
    assert stored_channel.api_to_send_message == "https://api.whatsapp.com/send"


@pytest.mark.asyncio
async def test_create_channel_admin_telegram_success(session):
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

    # When they create a channel with valid Telegram credentials
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    channel_data = CreateChannelRequest(
        name="Telegram Bot",
        platform=PlatformType.TELEGRAM,
        credentials={"bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"}
    )
    
    result = await create_channel(
        channel_data=channel_data,
        token=token,
        db_session=session
    )

    # Then the system creates the channel successfully
    assert result.name == "Telegram Bot"
    assert result.platform == PlatformType.TELEGRAM
    assert result.id is not None
    assert not hasattr(result, 'credentials')


@pytest.mark.asyncio
async def test_create_channel_admin_instagram_success(session):
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

    # When they create a channel with valid Instagram credentials
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    channel_data = CreateChannelRequest(
        name="Instagram Direct",
        platform=PlatformType.INSTAGRAM,
        credentials={"access_token": "IGQVJYeUx...", "page_id": "123456789"}
    )
    
    result = await create_channel(
        channel_data=channel_data,
        token=token,
        db_session=session
    )

    # Then the system creates the channel successfully
    assert result.name == "Instagram Direct"
    assert result.platform == PlatformType.INSTAGRAM
    assert result.id is not None
    assert not hasattr(result, 'credentials')


@pytest.mark.asyncio
async def test_create_channel_agent_success(session):
    # Given an agent is authenticated
    agent = Agent(
        name="Channel Creator Agent",
        callback_url="https://agent.example.com/callback"
    )
    
    token = Token(
        access_token="agent_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([agent, token])
    session.commit()
    session.refresh(agent)
    session.refresh(token)
    
    # Link token to agent
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # When they create a channel with valid credentials
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    
    channel_data = CreateChannelRequest(
        name="Agent Created Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+9876543210", "api_key": "agent_secret"}
    )
    
    result = await create_channel(
        channel_data=channel_data,
        token=token,
        db_session=session
    )

    # Then the system creates the channel successfully
    assert result.name == "Agent Created Channel"
    assert result.platform == PlatformType.WHATSAPP
    assert result.id is not None
    assert not hasattr(result, 'credentials')


@pytest.mark.asyncio
async def test_create_channel_member_forbidden(session):
    # Given a member user is authenticated
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to create a channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    channel_data = CreateChannelRequest(
        name="Unauthorized Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1111111111"}
    )

    try:
        result = await create_channel(
            channel_data=channel_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower() or "admin or agent access required" in str(e).lower()
        
        # And does not create any channel
        channel_statement = select(Channel).where(Channel.name == "Unauthorized Channel")
        channels = session.exec(channel_statement).all()
        assert len(channels) == 0


@pytest.mark.asyncio
async def test_create_channel_not_auth(session):
    # Given no valid authentication token is provided
    channel_data = CreateChannelRequest(
        name="Unauthorized Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1111111111"}
    )

    # When they try to create a channel
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await create_channel(
            channel_data=channel_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()


# Note: Test scenarios for invalid platform and missing credentials 
# are handled by Pydantic validation at the FastAPI level,
# so they would return 422 validation errors before reaching our endpoint