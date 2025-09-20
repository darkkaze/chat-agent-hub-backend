import pytest
from sqlmodel import create_engine, Session, SQLModel
from datetime import datetime, timezone, timedelta
from apis.auth import revoke_agent_token
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.helper import id_generator
import hashlib


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


def test_revoke_agent_token_success(session):
    """Test that admin can successfully revoke an agent token."""

    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hashlib.sha256("password".encode()).hexdigest(),
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    # Create admin token
    admin_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(admin_token)
    session.commit()
    session.refresh(admin_token)

    # Link admin token to user
    token_user = TokenUser(token_id=admin_token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # Create agent
    agent = Agent(
        name="Test Agent",
        webhook_url="http://localhost:8001/webhook",
        is_fire_and_forget=False,
        buffer_time_seconds=30,
        history_msg_count=10,
        recent_msg_window_minutes=60,
        activate_for_new_conversation=True,
        is_active=True
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    # Create agent token to revoke
    agent_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24*365),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(agent_token)
    session.commit()
    session.refresh(agent_token)

    # Link agent token to agent
    token_agent = TokenAgent(token_id=agent_token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # Call the function
    import asyncio

    async def run_test():
        result = await revoke_agent_token(
            agent_id=agent.id,
            token_id=agent_token.id,
            token=admin_token,
            db_session=session
        )
        return result

    result = asyncio.run(run_test())

    # Assertions
    assert "revoked successfully" in result.message
    assert agent_token.id in result.message

    # Verify token was revoked in database
    session.refresh(agent_token)
    assert agent_token.is_revoked == True


def test_revoke_agent_token_agent_not_found(session):
    """Test that 404 is returned when agent doesn't exist."""

    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hashlib.sha256("password".encode()).hexdigest(),
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    # Create admin token
    admin_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(admin_token)
    session.commit()
    session.refresh(admin_token)

    # Link admin token to user
    token_user = TokenUser(token_id=admin_token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # Call the function with non-existent agent ID
    import asyncio
    from fastapi import HTTPException

    async def run_test():
        with pytest.raises(HTTPException) as exc_info:
            await revoke_agent_token(
                agent_id="nonexistent_agent",
                token_id="some_token_id",
                token=admin_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 404
    assert result.detail == "Agent not found"


def test_revoke_agent_token_token_not_found(session):
    """Test that 404 is returned when token doesn't exist."""

    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hashlib.sha256("password".encode()).hexdigest(),
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    # Create admin token
    admin_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(admin_token)
    session.commit()
    session.refresh(admin_token)

    # Link admin token to user
    token_user = TokenUser(token_id=admin_token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # Create agent
    agent = Agent(
        name="Test Agent",
        webhook_url="http://localhost:8001/webhook",
        is_fire_and_forget=False,
        buffer_time_seconds=30,
        history_msg_count=10,
        recent_msg_window_minutes=60,
        activate_for_new_conversation=True,
        is_active=True
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    # Call the function with non-existent token ID
    import asyncio
    from fastapi import HTTPException

    async def run_test():
        with pytest.raises(HTTPException) as exc_info:
            await revoke_agent_token(
                agent_id=agent.id,
                token_id="nonexistent_token",
                token=admin_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 404
    assert result.detail == "Token not found or does not belong to this agent"


def test_revoke_agent_token_token_not_belongs_to_agent(session):
    """Test that 404 is returned when token belongs to different agent."""

    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hashlib.sha256("password".encode()).hexdigest(),
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    # Create admin token
    admin_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(admin_token)
    session.commit()
    session.refresh(admin_token)

    # Link admin token to user
    token_user = TokenUser(token_id=admin_token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # Create two agents
    agent1 = Agent(
        name="Test Agent 1",
        webhook_url="http://localhost:8001/webhook",
        is_fire_and_forget=False,
        buffer_time_seconds=30,
        history_msg_count=10,
        recent_msg_window_minutes=60,
        activate_for_new_conversation=True,
        is_active=True
    )
    agent2 = Agent(
        name="Test Agent 2",
        webhook_url="http://localhost:8002/webhook",
        is_fire_and_forget=False,
        buffer_time_seconds=30,
        history_msg_count=10,
        recent_msg_window_minutes=60,
        activate_for_new_conversation=True,
        is_active=True
    )
    session.add(agent1)
    session.add(agent2)
    session.commit()
    session.refresh(agent1)
    session.refresh(agent2)

    # Create agent token belonging to agent2
    agent2_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24*365),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(agent2_token)
    session.commit()
    session.refresh(agent2_token)

    # Link token to agent2
    token_agent = TokenAgent(token_id=agent2_token.id, agent_id=agent2.id)
    session.add(token_agent)
    session.commit()

    # Try to revoke agent2's token using agent1's ID
    import asyncio
    from fastapi import HTTPException

    async def run_test():
        with pytest.raises(HTTPException) as exc_info:
            await revoke_agent_token(
                agent_id=agent1.id,  # Different agent
                token_id=agent2_token.id,  # Token belongs to agent2
                token=admin_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 404
    assert result.detail == "Token not found or does not belong to this agent"


def test_revoke_agent_token_non_admin_forbidden(session):
    """Test that non-admin users get 403 forbidden."""

    # Create member user
    member_user = User(
        username="member",
        email="member@example.com",
        hashed_password=hashlib.sha256("password".encode()).hexdigest(),
        role=UserRole.MEMBER,
        is_active=True
    )
    session.add(member_user)
    session.commit()
    session.refresh(member_user)

    # Create member token
    member_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(member_token)
    session.commit()
    session.refresh(member_token)

    # Link member token to user
    token_user = TokenUser(token_id=member_token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # Create agent
    agent = Agent(
        name="Test Agent",
        webhook_url="http://localhost:8001/webhook",
        is_fire_and_forget=False,
        buffer_time_seconds=30,
        history_msg_count=10,
        recent_msg_window_minutes=60,
        activate_for_new_conversation=True,
        is_active=True
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    # Create agent token
    agent_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24*365),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(agent_token)
    session.commit()
    session.refresh(agent_token)

    # Link agent token to agent
    token_agent = TokenAgent(token_id=agent_token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # Call the function
    import asyncio
    from fastapi import HTTPException

    async def run_test():
        with pytest.raises(HTTPException) as exc_info:
            await revoke_agent_token(
                agent_id=agent.id,
                token_id=agent_token.id,
                token=member_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 403
    assert "Admin access required" in result.detail


def test_revoke_agent_token_already_revoked(session):
    """Test that already revoked token can be revoked again without error."""

    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hashlib.sha256("password".encode()).hexdigest(),
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    # Create admin token
    admin_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(admin_token)
    session.commit()
    session.refresh(admin_token)

    # Link admin token to user
    token_user = TokenUser(token_id=admin_token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # Create agent
    agent = Agent(
        name="Test Agent",
        webhook_url="http://localhost:8001/webhook",
        is_fire_and_forget=False,
        buffer_time_seconds=30,
        history_msg_count=10,
        recent_msg_window_minutes=60,
        activate_for_new_conversation=True,
        is_active=True
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    # Create already revoked agent token
    revoked_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24*365),
        created_at=datetime.now(timezone.utc),
        is_revoked=True  # Already revoked
    )
    session.add(revoked_token)
    session.commit()
    session.refresh(revoked_token)

    # Link revoked token to agent
    token_agent = TokenAgent(token_id=revoked_token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # Call the function
    import asyncio

    async def run_test():
        result = await revoke_agent_token(
            agent_id=agent.id,
            token_id=revoked_token.id,
            token=admin_token,
            db_session=session
        )
        return result

    result = asyncio.run(run_test())

    # Assertions - should succeed even if already revoked
    assert "revoked successfully" in result.message
    assert revoked_token.id in result.message

    # Verify token is still revoked
    session.refresh(revoked_token)
    assert revoked_token.is_revoked == True