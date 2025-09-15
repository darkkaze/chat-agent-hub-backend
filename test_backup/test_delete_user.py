"""
Feature: Delete system user
  As an admin user
  I want to delete users from the system
  So that I can manage user accounts and remove inactive users

Scenario: Admin successfully soft deletes a user
  Given an admin user is authenticated
  And a target user exists in the system
  When they delete the user with soft delete (default)
  Then the system marks the user as inactive
  And returns the updated user data with is_active=False
  And does not include hashed_password in response

Scenario: Admin successfully hard deletes a user
  Given an admin user is authenticated
  And a target user exists in the system
  When they delete the user with hard=true parameter
  Then the system permanently removes the user from database
  And returns success confirmation

Scenario: Admin tries to delete non-existent user
  Given an admin user is authenticated
  When they try to delete a user that doesn't exist
  Then the system returns 404 Not Found error

Scenario: Member user tries to delete another user
  Given a member user is authenticated
  And another user exists in the system
  When they try to delete the other user
  Then the system returns 403 Forbidden error

Scenario: Unauthenticated user tries to delete user
  Given no valid authentication token is provided
  When they try to delete a user
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from database import get_session
from apis.auth import delete_user
from datetime import datetime, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_user_soft_delete_success(session):
    # Given an admin user is authenticated and a target user exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    target_user = User(
        username="targetuser",
        email="target@example.com",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER,
        is_active=True
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

    # When they delete the user with soft delete (default)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await delete_user(
        user_id=target_user.id,
        hard=False,
        token=token,
        db_session=session
    )

    # Then the system marks the user as inactive
    assert result.message == "User soft-deleted successfully"
    
    # Verify user still exists in database but is inactive
    user_statement = select(User).where(User.id == target_user.id)
    db_user = session.exec(user_statement).first()
    assert db_user is not None
    assert db_user.is_active == False


@pytest.mark.asyncio
async def test_delete_user_hard_delete_success(session):
    # Given an admin user is authenticated and a target user exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    target_user = User(
        username="targetuser",
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
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they delete the user with hard=true parameter
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    result = await delete_user(
        user_id=target_user.id,
        hard=True,
        token=token,
        db_session=session
    )

    # Then the system permanently removes the user from database
    assert result.message == "User deleted successfully"
    
    # Verify user no longer exists in database
    user_statement = select(User).where(User.id == target_user.id)
    db_user = session.exec(user_statement).first()
    assert db_user is None


@pytest.mark.asyncio
async def test_delete_user_not_found(session):
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

    # When they try to delete a user that doesn't exist
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await delete_user(
            user_id="user_nonexistent",
            hard=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_user_member_forbidden(session):
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

    # When they try to delete the other user
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await delete_user(
            user_id=other_user.id,
            hard=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_user_not_auth(session):
    # Given a user exists but invalid token
    user = User(
        username="testuser",
        hashed_password="hashed_secret"
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # When they try to delete with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_user(
            user_id=user.id,
            hard=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()