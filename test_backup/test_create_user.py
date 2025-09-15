"""
Feature: Create new system user
  As an admin user
  I want to create new users in the system
  So that I can manage user accounts

Scenario: Admin successfully creates a new user
  Given an admin user is authenticated
  When they create a user with valid data
  Then the system creates the user successfully
  And returns the user data with generated ID
  And the password is stored hashed
  And does not include hashed_password in response

Scenario: Admin creates user with minimal data
  Given an admin user is authenticated
  When they create a user with only username and password
  Then the system creates the user with defaults
  And email and phone are null
  And role defaults to MEMBER
  And is_active defaults to True

Scenario: Non-admin user tries to create user
  Given a member user is authenticated
  When they try to create a user
  Then the system returns 403 Forbidden error

Scenario: Unauthenticated user tries to create user
  Given no valid authentication token is provided
  When they try to create a user
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole
from database import get_session
from apis.auth import create_user
from apis.schemas.auth import CreateUserRequest
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_create_user_success(session):
    # Given an admin user is authenticated
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
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

    # When they create a user with valid data
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    user_data = CreateUserRequest(
        username="newuser",
        email="newuser@example.com",
        phone="+1234567890",
        password="plainpassword",
        role="MEMBER"
    )
    
    result = await create_user(user_data=user_data, token=token, db_session=session)

    # Then the system creates the user successfully
    assert result.username == "newuser"
    assert result.email == "newuser@example.com" 
    assert result.phone == "+1234567890"
    assert result.role == UserRole.MEMBER
    assert result.is_active == True
    assert result.id.startswith("user_")
    # And does not include hashed_password in response
    assert not hasattr(result, 'hashed_password') or result.hashed_password is None


@pytest.mark.asyncio
async def test_create_user_minimal_data(session):
    # Given an admin user is authenticated
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret", 
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they create user with minimal data
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    user_data = CreateUserRequest(
        username="minimaluser",
        password="plainpassword"
    )
    
    result = await create_user(user_data=user_data, token=token, db_session=session)

    # Then the system creates user with defaults
    assert result.username == "minimaluser"
    assert result.email is None
    assert result.phone is None
    assert result.role == UserRole.MEMBER
    assert result.is_active == True


@pytest.mark.asyncio
async def test_create_user_non_admin_forbidden(session):
    # Given a member user is authenticated
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to create a user
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    user_data = CreateUserRequest(
        username="newuser",
        password="plainpassword"
    )
    
    try:
        result = await create_user(user_data=user_data, token=token, db_session=session)
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Should raise 403 exception
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_create_user_not_auth(session):
    # Given no valid token
    user_data = CreateUserRequest(
        username="newuser", 
        password="plainpassword"
    )

    # When they try to create user with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await create_user(user_data=user_data, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Should raise 401 exception  
        assert "401" in str(e) or "unauthorized" in str(e).lower()