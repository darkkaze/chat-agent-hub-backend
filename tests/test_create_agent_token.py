import pytest
from sqlmodel import create_engine, Session, SQLModel
from datetime import datetime, timezone, timedelta
from apis.auth import create_agent_token
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


def test_create_agent_token_success(session):
    """Test that admin can successfully create a new token for an agent."""

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

    # Call the function
    import asyncio

    async def run_test():
        result = await create_agent_token(
            agent_id=agent.id,
            token=admin_token,
            db_session=session
        )
        return result

    result = asyncio.run(run_test())

    # Assertions
    assert result.access_token is not None
    assert result.access_token.startswith("tkn_")
    assert result.expires_at is not None
    assert result.expires_at > datetime.now(timezone.utc)

    # Verify token was created in database
    from sqlmodel import select
    token_statement = select(Token).where(Token.access_token == result.access_token)
    created_token = session.exec(token_statement).first()
    assert created_token is not None
    assert created_token.is_revoked == False

    # Verify token is linked to agent
    token_agent_statement = select(TokenAgent).where(
        TokenAgent.token_id == created_token.id,
        TokenAgent.agent_id == agent.id
    )
    token_agent_link = session.exec(token_agent_statement).first()
    assert token_agent_link is not None


def test_create_agent_token_agent_not_found(session):
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
            await create_agent_token(
                agent_id="nonexistent_agent",
                token=admin_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 404
    assert result.detail == "Agent not found"


def test_create_agent_token_non_admin_forbidden(session):
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
            await create_agent_token(
                agent_id=agent.id,
                token=member_token,
                db_session=session
            )
        return exc_info.value

    result = asyncio.run(run_test())

    # Assertions
    assert result.status_code == 403
    assert "Admin access required" in result.detail


def test_create_agent_token_multiple_tokens_allowed(session):
    """Test that multiple tokens can be created for the same agent."""

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

    # Create first token
    import asyncio

    async def create_token():
        result = await create_agent_token(
            agent_id=agent.id,
            token=admin_token,
            db_session=session
        )
        return result

    token1 = asyncio.run(create_token())
    token2 = asyncio.run(create_token())

    # Assertions
    assert token1.access_token != token2.access_token
    assert token1.access_token is not None
    assert token2.access_token is not None

    # Verify both tokens exist in database
    from sqlmodel import select
    tokens_statement = (
        select(Token)
        .join(TokenAgent)
        .where(TokenAgent.agent_id == agent.id)
        .where(Token.is_revoked == False)
    )
    agent_tokens = session.exec(tokens_statement).all()
    assert len(agent_tokens) >= 2  # Should have at least the 2 we created

    # Verify unique access tokens
    access_tokens = {token.access_token for token in agent_tokens}
    assert token1.access_token in access_tokens
    assert token2.access_token in access_tokens