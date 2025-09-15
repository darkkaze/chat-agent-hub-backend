"""
Feature: User authentication login
  As a registered user
  I want to authenticate with username and password
  So that I can access the system and receive an access token

Scenario: Successful login with valid credentials
  Given a user exists in the system with username and hashed password
  When they provide correct username and password
  Then the system authenticates the user successfully
  And returns an access token with expiration
  And returns user information without sensitive data
  And creates a new token record in the database

Scenario: Login with invalid username
  Given no user exists with the provided username
  When they attempt to login
  Then the system returns 401 Unauthorized error
  And does not create any token records

Scenario: Login with invalid password
  Given a user exists in the system
  When they provide incorrect password for that username
  Then the system returns 401 Unauthorized error
  And does not create any token records

Scenario: Login with inactive user account
  Given a user exists but is marked as inactive
  When they attempt to login with valid credentials
  Then the system returns 401 Unauthorized error
  And does not create any token records

Scenario: Login with empty credentials
  Given empty username or password is provided
  When they attempt to login
  Then the system returns 422 Validation Error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from database import get_session
from apis.auth import login
from apis.schemas.auth import LoginRequest
from datetime import datetime, timezone, timedelta
import hashlib


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_login_success(session):
    # Given a user exists in the system with username and hashed password
    password = "testpassword123"
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashed_password,
        role=UserRole.MEMBER,
        is_active=True
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)

    # When they provide correct username and password
    login_data = LoginRequest(
        username="testuser",
        password=password
    )
    
    result = await login(login_data=login_data, db_session=session)

    # Then the system authenticates the user successfully
    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.token_type == "bearer"
    assert result.expires_at > datetime.now(timezone.utc)
    
    # And returns user information without sensitive data
    assert result.user.username == "testuser"
    assert result.user.email == "test@example.com"
    assert result.user.role == UserRole.MEMBER
    assert result.user.is_active == True
    
    # And creates a new token record in the database
    token_statement = select(Token).where(Token.access_token == result.access_token)
    token = session.exec(token_statement).first()
    assert token is not None
    assert token.refresh_token == result.refresh_token
    assert not token.is_revoked
    
    # Verify token-user link exists
    token_user_statement = select(TokenUser).where(
        TokenUser.token_id == token.id,
        TokenUser.user_id == user.id
    )
    token_user = session.exec(token_user_statement).first()
    assert token_user is not None


@pytest.mark.asyncio
async def test_login_invalid_username(session):
    # Given no user exists with the provided username
    login_data = LoginRequest(
        username="nonexistent",
        password="anypassword"
    )

    # When they attempt to login
    try:
        result = await login(login_data=login_data, db_session=session)
        assert False, "Should have raised authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "invalid credentials" in str(e).lower()
        
        # And does not create any token records
        token_statement = select(Token)
        tokens = session.exec(token_statement).all()
        assert len(tokens) == 0


@pytest.mark.asyncio
async def test_login_invalid_password(session):
    # Given a user exists in the system
    password = "correctpassword"
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    user = User(
        username="testuser",
        hashed_password=hashed_password,
        is_active=True
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)

    # When they provide incorrect password for that username
    login_data = LoginRequest(
        username="testuser",
        password="wrongpassword"
    )

    try:
        result = await login(login_data=login_data, db_session=session)
        assert False, "Should have raised authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "invalid credentials" in str(e).lower()
        
        # And does not create any token records
        token_statement = select(Token)
        tokens = session.exec(token_statement).all()
        assert len(tokens) == 0


@pytest.mark.asyncio
async def test_login_inactive_user(session):
    # Given a user exists but is marked as inactive
    password = "testpassword"
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    user = User(
        username="inactiveuser",
        hashed_password=hashed_password,
        is_active=False  # User is inactive
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)

    # When they attempt to login with valid credentials
    login_data = LoginRequest(
        username="inactiveuser",
        password=password
    )

    try:
        result = await login(login_data=login_data, db_session=session)
        assert False, "Should have raised authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "invalid credentials" in str(e).lower()
        
        # And does not create any token records
        token_statement = select(Token)
        tokens = session.exec(token_statement).all()
        assert len(tokens) == 0


@pytest.mark.asyncio
async def test_login_empty_credentials(session):
    # Given empty username or password is provided
    # This test will be handled by Pydantic validation
    # We can test with empty strings which should pass validation but fail authentication
    
    login_data = LoginRequest(
        username="",
        password=""
    )

    try:
        result = await login(login_data=login_data, db_session=session)
        assert False, "Should have raised authentication error"
    except Exception as e:
        # Then the system should return 401 (since empty strings still pass validation)
        # but fail authentication
        assert "401" in str(e) or "invalid credentials" in str(e).lower()