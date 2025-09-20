import pytest
from sqlmodel import create_engine, Session, SQLModel
from datetime import datetime, timezone, timedelta
from apis.auth import get_agent_tokens
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


def test_get_agent_tokens_success(session):
    """Test that admin can successfully get active agent tokens."""

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

    # Create active agent token
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
        result = await get_agent_tokens(
            agent_id=agent.id,
            token=admin_token,
            db_session=session
        )
        return result

    result = asyncio.run(run_test())

    # Assertions
    assert len(result.tokens) == 1
    assert result.tokens[0].access_token == agent_token.access_token
    assert result.tokens[0].expires_at == agent_token.expires_at


def test_get_agent_tokens_agent_not_found(session):
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
            await get_agent_tokens(
                agent_id="nonexistent_agent",
                token=admin_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 404
    assert result.detail == "Agent not found"


def test_get_agent_tokens_non_admin_forbidden(session):
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

    # Call the function
    import asyncio
    from fastapi import HTTPException

    async def run_test():
        with pytest.raises(HTTPException) as exc_info:
            await get_agent_tokens(
                agent_id=agent.id,
                token=member_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 403
    assert "Admin access required" in result.detail


def test_get_agent_tokens_filters_revoked(session):
    """Test that revoked tokens are not returned."""

    # Create admin user and token
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

    # Create revoked agent token
    revoked_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24*365),
        created_at=datetime.now(timezone.utc),
        is_revoked=True  # Revoked
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
        result = await get_agent_tokens(
            agent_id=agent.id,
            token=admin_token,
            db_session=session
        )
        return result

    result = asyncio.run(run_test())

    # Assertions - should not return revoked token
    assert len(result.tokens) == 0


def test_get_agent_tokens_filters_expired(session):
    """Test that expired tokens are not returned."""

    # Create admin user and token
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

    # Create expired agent token
    expired_token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        is_revoked=False
    )
    session.add(expired_token)
    session.commit()
    session.refresh(expired_token)

    # Link expired token to agent
    token_agent = TokenAgent(token_id=expired_token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # Call the function
    import asyncio

    async def run_test():
        result = await get_agent_tokens(
            agent_id=agent.id,
            token=admin_token,
            db_session=session
        )
        return result

    result = asyncio.run(run_test())

    # Assertions - should not return expired token
    assert len(result.tokens) == 0


def test_get_agent_tokens_multiple_active_tokens(session):
    """Test that multiple active tokens are returned."""

    # Create admin user and token
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

    # Create two active agent tokens
    token1 = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24*365),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(token1)
    session.commit()
    session.refresh(token1)

    token2 = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24*365),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(token2)
    session.commit()
    session.refresh(token2)

    # Link both tokens to agent
    token_agent1 = TokenAgent(token_id=token1.id, agent_id=agent.id)
    token_agent2 = TokenAgent(token_id=token2.id, agent_id=agent.id)
    session.add(token_agent1)
    session.add(token_agent2)
    session.commit()

    # Call the function
    import asyncio

    async def run_test():
        result = await get_agent_tokens(
            agent_id=agent.id,
            token=admin_token,
            db_session=session
        )
        return result

    result = asyncio.run(run_test())

    # Assertions - should return both active tokens
    assert len(result.tokens) == 2
    returned_tokens = {token.access_token for token in result.tokens}
    expected_tokens = {token1.access_token, token2.access_token}
    assert returned_tokens == expected_tokens