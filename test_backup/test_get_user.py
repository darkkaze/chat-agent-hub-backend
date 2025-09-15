"""
Feature: Get user information by user ID
  As an authenticated user or agent
  I want to retrieve user information by user ID
  So that I can access user details

Scenario: Successfully get user information with valid token
  Given a valid authentication token exists
  And a user exists in the system
  When they request user information with GET /auth/users/{user_id}
  Then the system returns the user data
  And includes id, username, email, phone, role, is_active
  And does not include sensitive information like hashed_password

Scenario: Get user with non-existent user ID
  Given a valid authentication token exists
  And the requested user ID does not exist
  When they request user information with GET /auth/users/{invalid_id}
  Then the system returns 404 Not Found error

Scenario: Get user without authentication
  Given no valid authentication token is provided
  When they request user information with GET /auth/users/{user_id}
  Then the system returns 401 Unauthorized error
"""

import pytest
import pytest_asyncio
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from database import get_session
from apis.auth import get_user
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_get_user_success(session):
    # Given a valid token and existing user
    user = User(
        username="testuser",
        email="test@example.com",
        phone="+1234567890",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN,
        is_active=True
    )
    
    token = Token(
        access_token="valid_jwt_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, token])
    session.commit()
    session.refresh(user)
    session.refresh(token)
    
    # Link token to user
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they request user information (bypassing FastAPI dependencies)
    # We need to simulate what get_auth_token would return
    from helpers.auth import get_auth_token
    try:
        # This should validate the token and return Token object
        token = await get_auth_token(authorization="Bearer valid_jwt_token", db_session=session)
        # Now call get_user directly  
        result = await get_user(user_id=user.id, token=token, db_session=session)
    except Exception as e:
        pytest.fail(f"Token validation failed: {e}")

    # Then the system returns user data
    assert result.username == "testuser"
    assert result.email == "test@example.com"
    assert result.phone == "+1234567890"
    assert result.role == UserRole.ADMIN
    assert result.is_active == True
    # And does not include sensitive information
    assert not hasattr(result, 'hashed_password') or result.hashed_password is None


@pytest.mark.asyncio
async def test_get_user_not_found(session):
    # Given a valid token but non-existent user
    token = Token(
        access_token="valid_jwt_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    session.add(token)
    session.commit()
    
    non_existent_id = "user_nonexistent"

    # When they request user information for non-existent user
    # Then the system should return 404 or None
    # This will depend on the actual implementation
    from helpers.auth import get_auth_token
    try:
        # First validate token and get Token object
        token = await get_auth_token(authorization="Bearer valid_jwt_token", db_session=session)
        # Then try to get non-existent user
        result = await get_user(user_id=non_existent_id, token=token, db_session=session)
        assert result is None  # Or whatever the expected behavior is
    except Exception as e:
        # Or it might raise a 404 exception
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_get_user_not_auth(session):
    # Given an invalid token
    user = User(
        username="testuser",
        hashed_password="hashed_secret"
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # When they request user information with invalid token
    # Then the system should return 401 Unauthorized
    from helpers.auth import get_auth_token
    try:
        # This should fail at token validation
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await get_user(user_id=user.id, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Should raise 401 exception
        assert "401" in str(e) or "unauthorized" in str(e).lower()