"""
Feature: Update user information
  As an admin or the user themselves
  I want to update user information
  So that I can maintain accurate user data

Scenario: Admin successfully updates another user
  Given an admin user is authenticated
  And another user exists in the system
  When they update the user with valid data
  Then the system updates the user successfully
  And returns the updated user data
  And does not include hashed_password in response

Scenario: User successfully updates their own profile
  Given a member user is authenticated
  When they update their own user data
  Then the system updates their profile successfully
  And returns the updated user data

Scenario: Member user tries to update another user
  Given a member user is authenticated
  And another user exists in the system
  When they try to update the other user
  Then the system returns 403 Forbidden error

Scenario: Unauthenticated user tries to update user
  Given no valid authentication token is provided
  When they try to update a user
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole
from database import get_session
from apis.auth import update_user
from apis.schemas.auth import UpdateUserRequest
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_update_user_admin_success(session):
    # Given an admin user is authenticated and another user exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    target_user = User(
        username="targetuser",
        email="old@example.com",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, target_user, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(target_user)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they update the target user
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    update_data = UpdateUserRequest(
        email="updated@example.com",
        phone="+9876543210"
    )
    
    result = await update_user(
        user_id=target_user.id, 
        user_data=update_data, 
        token=token, 
        db_session=session
    )

    # Then the system updates the user successfully
    assert result.username == "targetuser"  # Unchanged
    assert result.email == "updated@example.com"  # Updated
    assert result.phone == "+9876543210"  # Updated
    assert result.role == UserRole.MEMBER  # Unchanged
    # And does not include hashed_password
    assert not hasattr(result, 'hashed_password') or result.hashed_password is None


@pytest.mark.asyncio
async def test_update_user_self_success(session):
    # Given a member user is authenticated
    member_user = User(
        username="member",
        email="member@example.com",
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

    # When they update their own profile
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    update_data = UpdateUserRequest(
        email="newemail@example.com",
        phone="+1111111111"
    )
    
    result = await update_user(
        user_id=member_user.id, 
        user_data=update_data, 
        token=token, 
        db_session=session
    )

    # Then the system updates their profile successfully
    assert result.username == "member"
    assert result.email == "newemail@example.com"
    assert result.phone == "+1111111111"
    assert result.role == UserRole.MEMBER


@pytest.mark.asyncio
async def test_update_user_member_forbidden(session):
    # Given a member user is authenticated and another user exists
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    other_user = User(
        username="otheruser",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, other_user, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(other_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to update the other user
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    update_data = UpdateUserRequest(
        email="hacked@example.com"
    )
    
    try:
        result = await update_user(
            user_id=other_user.id, 
            user_data=update_data, 
            token=token, 
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Should raise 403 exception
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_update_user_not_auth(session):
    # Given a user exists but invalid token
    user = User(
        username="testuser",
        hashed_password="hashed_secret"
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # When they try to update with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await update_user(
            user_id=user.id, 
            user_data=UpdateUserRequest(email="hack@example.com"), 
            token=token, 
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Should raise 401 exception
        assert "401" in str(e) or "unauthorized" in str(e).lower()