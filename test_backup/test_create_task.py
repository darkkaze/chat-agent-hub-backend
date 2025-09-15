"""
Feature: Create new task
  As an authenticated user or agent
  I want to create a new task
  So that I can track work items in boards

Scenario: Successfully create task with all fields
  Given an authenticated user exists
  When they create a task with title, description, column, and chat_id
  Then the system creates the task successfully
  And returns the task information
  And stores the task in the database

Scenario: Create task with minimal data
  Given an authenticated user exists
  When they create a task with only title and column
  Then the system creates the task successfully
  And description defaults to empty string
  And chat_id is null

Scenario: Create task without authentication
  Given no valid authentication token is provided
  When they try to create a task
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.channels import Channel, Chat  # Need for foreign keys
from database import get_session
from apis.tasks import create_task
from apis.schemas.tasks import CreateTaskRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_create_task_with_all_fields(session):
    # Given an authenticated user exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    # Create a chat for association
    channel = Channel(
        name="Test Channel",
        platform="WHATSAPP"
    )
    
    session.add_all([user, token, channel])
    session.commit()
    session.refresh(user)
    session.refresh(token)
    session.refresh(channel)
    
    chat = Chat(
        name="Test Chat",
        external_id="ext_chat_123",
        channel_id=channel.id
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    
    # Link token to user
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they create a task with title, description, column, and chat_id
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    task_data = CreateTaskRequest(
        title="Complete API Implementation",
        description="Implement all CRUD operations for tasks",
        column="In Progress",
        chat_id=chat.id
    )
    
    result = await create_task(
        task_data=task_data,
        token=token,
        db_session=session
    )

    # Then the system creates the task successfully
    assert result.title == "Complete API Implementation"
    assert result.description == "Implement all CRUD operations for tasks"
    assert result.column == "In Progress"
    assert result.chat_id == chat.id
    assert result.id is not None
    
    # And stores the task in the database
    task_statement = select(Task).where(Task.id == result.id)
    stored_task = session.exec(task_statement).first()
    assert stored_task is not None
    assert stored_task.title == "Complete API Implementation"
    assert stored_task.description == "Implement all CRUD operations for tasks"
    assert stored_task.column == "In Progress"
    assert stored_task.chat_id == chat.id


@pytest.mark.asyncio
async def test_create_task_minimal_data(session):
    # Given an authenticated user exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, token])
    session.commit()
    session.refresh(user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they create a task with only title and column
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    task_data = CreateTaskRequest(
        title="Simple Task",
        column="To Do"
        # description defaults to ""
        # chat_id defaults to None
    )
    
    result = await create_task(
        task_data=task_data,
        token=token,
        db_session=session
    )

    # Then the system creates the task successfully
    assert result.title == "Simple Task"
    assert result.column == "To Do"
    # And description defaults to empty string
    assert result.description == ""
    # And chat_id is null
    assert result.chat_id is None
    assert result.id is not None


@pytest.mark.asyncio
async def test_create_task_not_auth(session):
    # Given no valid authentication token is provided
    task_data = CreateTaskRequest(
        title="Unauthorized Task",
        column="To Do"
    )

    # When they try to create a task
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await create_task(
            task_data=task_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()