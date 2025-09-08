"""
Feature: Disconnect a channel
  As an admin user or agent
  I want to disconnect/delete a communication channel
  So that I can remove channels that are no longer needed

Scenario: Admin successfully deletes channel
  Given an admin user is authenticated
  And a channel exists in the system
  When they delete the channel with DELETE /channels/{channel_id}
  Then the system removes the channel successfully
  And returns success confirmation message
  And removes any associated UserChannelPermission records
  And removes any associated ChannelAgent records

Scenario: Agent successfully deletes channel
  Given an agent is authenticated
  And a channel exists in the system
  When they delete the channel with DELETE /channels/{channel_id}
  Then the system removes the channel successfully
  And returns success confirmation message
  And removes any associated records

Scenario: Member user tries to delete channel
  Given a member user is authenticated
  And a channel exists in the system
  When they try to delete the channel
  Then the system returns 403 Forbidden error
  And does not delete the channel

Scenario: Delete non-existent channel
  Given an admin user is authenticated
  When they try to delete a non-existent channel
  Then the system returns 404 Not Found error

Scenario: Delete channel without authentication
  Given no valid authentication token is provided
  When they try to delete a channel
  Then the system returns 401 Unauthorized error

Scenario: Delete channel with associated agent relationships
  Given an admin user is authenticated
  And a channel exists with agent associations (ChannelAgent records)
  When they delete the channel
  Then the system removes the channel successfully
  And removes all associated ChannelAgent records
  And returns success confirmation message
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.channels import Channel, UserChannelPermission, PlatformType, ChannelAgent
from database import get_session
from apis.channels import delete_channel
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_channel_admin_success(session):
    # Given an admin user is authenticated and a channel exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Channel to Delete",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
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
    
    # Add some associated records to test cleanup
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    session.add(member_user)
    session.commit()
    session.refresh(member_user)
    
    # Create UserChannelPermission
    permission = UserChannelPermission(
        user_id=member_user.id,
        channel_id=channel.id
    )
    session.add(permission)
    session.commit()

    # When they delete the channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    result = await delete_channel(channel_id=channel.id, token=token, db_session=session)

    # Then the system removes the channel successfully
    assert result.message == "Channel deleted successfully"
    
    # And removes the channel from database
    channel_statement = select(Channel).where(Channel.id == channel.id)
    deleted_channel = session.exec(channel_statement).first()
    assert deleted_channel is None
    
    # And removes any associated UserChannelPermission records
    permission_statement = select(UserChannelPermission).where(UserChannelPermission.channel_id == channel.id)
    permissions = session.exec(permission_statement).all()
    assert len(permissions) == 0


@pytest.mark.asyncio
async def test_delete_channel_agent_success(session):
    # Given an agent is authenticated and a channel exists
    agent = Agent(
        name="Channel Deleter Agent",
        callback_url="https://agent.example.com/callback"
    )
    
    channel = Channel(
        name="Agent Deleted Channel",
        platform=PlatformType.TELEGRAM,
        credentials={"bot_token": "secret_token"}
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

    # When they delete the channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    result = await delete_channel(channel_id=channel.id, token=token, db_session=session)

    # Then the system removes the channel successfully
    assert result.message == "Channel deleted successfully"
    
    # And removes the channel from database
    channel_statement = select(Channel).where(Channel.id == channel.id)
    deleted_channel = session.exec(channel_statement).first()
    assert deleted_channel is None


@pytest.mark.asyncio
async def test_delete_channel_member_forbidden(session):
    # Given a member user is authenticated and a channel exists
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    channel = Channel(
        name="Protected Channel",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
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

    # When they try to delete the channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await delete_channel(channel_id=channel.id, token=token, db_session=session)
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower() or "admin or agent access required" in str(e).lower()
        
        # And does not delete the channel
        channel_statement = select(Channel).where(Channel.id == channel.id)
        existing_channel = session.exec(channel_statement).first()
        assert existing_channel is not None
        assert existing_channel.name == "Protected Channel"


@pytest.mark.asyncio
async def test_delete_channel_not_found(session):
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

    # When they try to delete a non-existent channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await delete_channel(channel_id="channel_nonexistent", token=token, db_session=session)
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_channel_not_auth(session):
    # Given a channel exists but no valid authentication
    channel = Channel(
        name="Unauthorized Delete",
        platform=PlatformType.WHATSAPP,
        credentials={"phone": "+1234567890"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)

    # When they try to delete the channel without authentication
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_channel(channel_id=channel.id, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_channel_with_agent_associations(session):
    # Given an admin user is authenticated and a channel with agent associations exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    channel = Channel(
        name="Channel with Agents",
        platform=PlatformType.INSTAGRAM,
        credentials={"access_token": "secret"}
    )
    
    agent1 = Agent(
        name="Agent 1",
        callback_url="https://agent1.example.com/callback"
    )
    
    agent2 = Agent(
        name="Agent 2", 
        callback_url="https://agent2.example.com/callback"
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, channel, agent1, agent2, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(channel)
    session.refresh(agent1)
    session.refresh(agent2)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    
    # Create ChannelAgent associations
    channel_agent1 = ChannelAgent(channel_id=channel.id, agent_id=agent1.id)
    channel_agent2 = ChannelAgent(channel_id=channel.id, agent_id=agent2.id)
    session.add_all([channel_agent1, channel_agent2])
    session.commit()

    # When they delete the channel
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    result = await delete_channel(channel_id=channel.id, token=token, db_session=session)

    # Then the system removes the channel successfully
    assert result.message == "Channel deleted successfully"
    
    # And removes the channel from database
    channel_statement = select(Channel).where(Channel.id == channel.id)
    deleted_channel = session.exec(channel_statement).first()
    assert deleted_channel is None
    
    # And removes all associated ChannelAgent records
    channel_agent_statement = select(ChannelAgent).where(ChannelAgent.channel_id == channel.id)
    channel_agents = session.exec(channel_agent_statement).all()
    assert len(channel_agents) == 0