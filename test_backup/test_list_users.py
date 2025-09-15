"""
Feature: List system users
  As an authenticated user or agent
  I want to retrieve a list of system users
  So that I can see user information

Scenario: Successfully list active users with valid token
  Given a valid authentication token exists
  And there are users in the system with different statuses
  When they request the user list with GET /auth/users
  Then the system returns only active users by default
  And each user includes id, username, email, phone, role, is_active
  And does not include sensitive information like hashed_password

Scenario: Successfully list inactive users when explicitly requested
  Given a valid authentication token exists
  And there are inactive users in the system
  When they request the user list with GET /auth/users?is_active=false
  Then the system returns only inactive users
  And does not include sensitive information

Scenario: List users without authentication
  Given no valid authentication token is provided
  When they request the user list with GET /auth/users
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, UserRole
from database import get_session
from apis.auth import list_users
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_list_users_success(session):
    # Given a valid token and users with different statuses
    active_user1 = User(
        username="active1",
        email="active1@example.com",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN,
        is_active=True
    )
    
    active_user2 = User(
        username="active2",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER,
        is_active=True
    )
    
    inactive_user = User(
        username="inactive1",
        email="inactive@example.com",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER,
        is_active=False
    )
    
    token = Token(
        access_token="valid_jwt_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([active_user1, active_user2, inactive_user, token])
    session.commit()

    # When they request user list (default is_active=True)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer valid_jwt_token", db_session=session)
    result = await list_users(is_active=True, token=token, db_session=session)

    # Then the system returns only active users
    assert len(result) == 2
    usernames = [user.username for user in result]
    assert "active1" in usernames
    assert "active2" in usernames
    assert "inactive1" not in usernames
    
    # And does not include sensitive information
    for user in result:
        assert not hasattr(user, 'hashed_password') or user.hashed_password is None


@pytest.mark.asyncio
async def test_list_users_inactive(session):
    # Given users with different statuses
    active_user = User(
        username="active1",
        hashed_password="hashed_secret",
        is_active=True
    )
    
    inactive_user = User(
        username="inactive1",
        hashed_password="hashed_secret",
        is_active=False
    )
    
    token = Token(
        access_token="valid_jwt_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([active_user, inactive_user, token])
    session.commit()

    # When they request inactive users explicitly
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer valid_jwt_token", db_session=session)
    result = await list_users(is_active=False, token=token, db_session=session)

    # Then the system returns only inactive users
    assert len(result) == 1
    assert result[0].username == "inactive1"
    assert result[0].is_active == False


@pytest.mark.asyncio
async def test_list_users_not_auth(session):
    # Given users exist but invalid token
    user = User(
        username="testuser",
        hashed_password="hashed_secret"
    )
    session.add(user)
    session.commit()

    # When they request user list with invalid token
    from helpers.auth import get_auth_token
    try:
        # This should fail at token validation
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await list_users(is_active=True, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Should raise 401 exception
        assert "401" in str(e) or "unauthorized" in str(e).lower()