"""
Feature: Update task
  As an authenticated user or agent
  I want to update an existing task
  So that I can modify task information

Scenario: Successfully update task with all fields
  Given an authenticated user exists
  And a task exists
  When they update the task with new title, description, and column
  Then the system updates the task successfully
  And returns the updated task information

Scenario: Update task with partial data
  Given an authenticated user exists
  And a task exists
  When they update only the title
  Then the system updates only the title
  And other fields remain unchanged

Scenario: Update non-existent task
  Given an authenticated user exists
  When they try to update a non-existent task
  Then the system returns 404 Not Found error

Scenario: Update task without authentication
  Given no valid authentication token is provided
  When they try to update a task
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import update_task
from apis.schemas.tasks import UpdateTaskRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_update_task_all_fields(session):
    # Given an authenticated user exists and a task exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Original Task",
        description="Original description",
        column="To Do"
    )
    
    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, task, token])
    session.commit()
    session.refresh(user)
    session.refresh(task)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they update the task with new title, description, and column
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    update_data = UpdateTaskRequest(
        title="Updated Task",
        description="Updated description",
        column="In Progress"
    )
    
    result = await update_task(
        task_id=task.id,
        task_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates the task successfully
    assert result.title == "Updated Task"
    assert result.description == "Updated description"
    assert result.column == "In Progress"
    assert result.id == task.id


@pytest.mark.asyncio
async def test_update_task_partial_data(session):
    # Given an authenticated user exists and a task exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Original Task",
        description="Original description",
        column="To Do"
    )
    
    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, task, token])
    session.commit()
    session.refresh(user)
    session.refresh(task)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they update only the title
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    update_data = UpdateTaskRequest(
        title="Updated Title Only"
        # description and column not provided
    )
    
    result = await update_task(
        task_id=task.id,
        task_data=update_data,
        token=token,
        db_session=session
    )

    # Then the system updates only the title
    assert result.title == "Updated Title Only"
    # And other fields remain unchanged
    assert result.description == "Original description"
    assert result.column == "To Do"


@pytest.mark.asyncio
async def test_update_task_not_found(session):
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

    # When they try to update a non-existent task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    update_data = UpdateTaskRequest(title="Updated Task")
    
    try:
        result = await update_task(
            task_id="task_nonexistent",
            task_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_update_task_not_auth(session):
    # Given a task exists but no valid authentication
    task = Task(
        title="Unauthorized Task",
        column="To Do"
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    update_data = UpdateTaskRequest(title="Updated Task")

    # When they try to update a task with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await update_task(
            task_id=task.id,
            task_data=update_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()