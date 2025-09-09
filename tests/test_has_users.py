"""
Feature: Check if users exist in the system
  As a system administrator
  I want to know if any users exist in the system
  So that I can determine if onboarding is needed

Scenario: No users exist in system
  Given no users exist in the database
  When I check if users exist
  Then the system returns false

Scenario: Users exist in system
  Given at least one user exists in the database
  When I check if users exist
  Then the system returns true

Scenario: Only inactive users exist
  Given only inactive users exist in the database
  When I check if users exist
  Then the system returns true (counts all users regardless of status)
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, UserRole
from database import get_session
from apis.auth import has_users


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_has_users_empty_database(session):
    # Given no users exist in the database
    # When I check if users exist
    result = await has_users(db_session=session)
    
    # Then the system returns false
    assert result == {"has_users": False}


@pytest.mark.asyncio
async def test_has_users_with_active_user(session):
    # Given at least one active user exists in the database
    user = User(
        username="testuser",
        hashed_password="hashed_password",
        role=UserRole.ADMIN,
        is_active=True
    )
    
    session.add(user)
    session.commit()
    
    # When I check if users exist
    result = await has_users(db_session=session)
    
    # Then the system returns true
    assert result == {"has_users": True}


@pytest.mark.asyncio
async def test_has_users_with_inactive_user(session):
    # Given only inactive users exist in the database
    user = User(
        username="inactiveuser",
        hashed_password="hashed_password", 
        role=UserRole.MEMBER,
        is_active=False
    )
    
    session.add(user)
    session.commit()
    
    # When I check if users exist
    result = await has_users(db_session=session)
    
    # Then the system returns true (counts all users regardless of status)
    assert result == {"has_users": True}


@pytest.mark.asyncio
async def test_has_users_with_multiple_users(session):
    # Given multiple users exist in the database
    user1 = User(
        username="user1",
        hashed_password="hashed_password",
        role=UserRole.ADMIN,
        is_active=True
    )
    user2 = User(
        username="user2",
        hashed_password="hashed_password",
        role=UserRole.MEMBER,
        is_active=False
    )
    
    session.add_all([user1, user2])
    session.commit()
    
    # When I check if users exist
    result = await has_users(db_session=session)
    
    # Then the system returns true
    assert result == {"has_users": True}