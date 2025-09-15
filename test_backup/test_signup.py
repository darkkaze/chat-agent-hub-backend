"""
Feature: Initial admin signup
  As a new system
  I want to allow creating the first admin user without authentication
  So that the system can be initialized

Scenario: Successfully create first admin user
  Given no users exist in the database
  When a valid signup request is made
  Then the system creates an admin user
  And returns authentication tokens
  And the user has ADMIN role

Scenario: Attempt signup when users already exist
  Given at least one user already exists in the database
  When a signup request is made
  Then the system returns 403 Forbidden error
  And no new user is created

Scenario: Signup with minimal data
  Given no users exist in the database
  When a signup request is made with only username and password
  Then the system creates an admin user successfully
  And email is optional

Scenario: Verify token is valid after signup
  Given no users exist in the database
  When a successful signup is completed
  Then the returned token can be used for authenticated requests
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole
from database import get_session
from apis.auth import signup
from apis.schemas.auth import SignupRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_signup_success_empty_database(session):
    # Given no users exist in the database
    # When a valid signup request is made
    signup_data = SignupRequest(
        username="admin",
        password="secure123",
        email="admin@example.com"
    )
    
    result = await signup(signup_data=signup_data, db_session=session)
    
    # Then the system creates an admin user and returns authentication tokens
    assert result.access_token.startswith("tkn_")
    assert result.refresh_token.startswith("ref_")
    assert result.token_type == "bearer"
    assert result.expires_at > datetime.now(timezone.utc)
    
    # And the user has ADMIN role
    assert result.user.username == "admin"
    assert result.user.email == "admin@example.com"
    assert result.user.role == UserRole.ADMIN
    assert result.user.is_active is True


@pytest.mark.asyncio
async def test_signup_forbidden_when_users_exist(session):
    # Given at least one user already exists in the database
    existing_user = User(
        username="existing",
        hashed_password="hashed_password",
        role=UserRole.MEMBER
    )
    session.add(existing_user)
    session.commit()
    
    # When a signup request is made
    signup_data = SignupRequest(
        username="admin",
        password="secure123"
    )
    
    try:
        result = await signup(signup_data=signup_data, db_session=session)
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_signup_minimal_data(session):
    # Given no users exist in the database
    # When a signup request is made with only username and password
    signup_data = SignupRequest(
        username="admin",
        password="secure123"
        # email is optional
    )
    
    result = await signup(signup_data=signup_data, db_session=session)
    
    # Then the system creates an admin user successfully
    assert result.user.username == "admin"
    assert result.user.email is None  # Email is optional
    assert result.user.role == UserRole.ADMIN
    assert result.access_token.startswith("tkn_")


@pytest.mark.asyncio
async def test_signup_token_validity(session):
    # Given no users exist in the database
    signup_data = SignupRequest(
        username="admin",
        password="secure123",
        email="admin@example.com"
    )
    
    # When a successful signup is completed
    result = await signup(signup_data=signup_data, db_session=session)
    
    # Then the returned token can be used for authenticated requests
    # Verify token exists in database and is linked to user
    from helpers.auth import get_auth_token
    
    token = await get_auth_token(
        authorization=f"Bearer {result.access_token}", 
        db_session=session
    )
    
    assert token.access_token == result.access_token
    # Compare timestamps without timezone (database doesn't store timezone)
    assert token.expires_at.replace(tzinfo=None) == result.expires_at.replace(tzinfo=None)
    assert not token.is_revoked


@pytest.mark.asyncio
async def test_signup_creates_admin_user_in_database(session):
    # Given no users exist in the database
    signup_data = SignupRequest(
        username="admin",
        password="secure123"
    )
    
    # When signup is completed
    result = await signup(signup_data=signup_data, db_session=session)
    
    # Then user is actually created in database with correct data
    from sqlmodel import select
    user_statement = select(User).where(User.username == "admin")
    created_user = session.exec(user_statement).first()
    
    assert created_user is not None
    assert created_user.username == "admin"
    assert created_user.role == UserRole.ADMIN
    assert created_user.is_active is True
    # Password should be hashed
    assert created_user.hashed_password != "secure123"
    assert len(created_user.hashed_password) == 64  # SHA256 hex length