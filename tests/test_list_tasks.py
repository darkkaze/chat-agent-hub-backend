"""
Feature: List tasks
  As an authenticated user or agent
  I want to retrieve a list of tasks
  So that I can see all work items

Scenario: Successfully list all tasks
  Given an authenticated user exists
  And there are tasks in the system
  When they request the task list with GET /tasks
  Then the system returns all tasks
  And each task includes basic information (no notes/documents in list)

Scenario: List tasks when none exist
  Given an authenticated user exists
  And no tasks exist in the system
  When they request the task list
  Then the system returns an empty list

Scenario: List tasks without authentication
  Given no valid authentication token is provided
  When they request the task list
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import list_tasks
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_list_tasks_success(session):
    # Given an authenticated user exists and tasks exist
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task1 = Task(
        title="First Task",
        description="Description 1",
        column="To Do"
    )
    
    task2 = Task(
        title="Second Task",
        description="Description 2",
        column="In Progress"
    )
    
    task3 = Task(
        title="Third Task",
        description="Description 3",
        column="Done"
    )
    
    token = Token(
        access_token="user_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, task1, task2, task3, token])
    session.commit()
    session.refresh(user)
    session.refresh(task1)
    session.refresh(task2)
    session.refresh(task3)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they request the task list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    result = await list_tasks(token=token, db_session=session)

    # Then the system returns all tasks
    assert len(result) == 3
    task_titles = [task.title for task in result]
    assert "First Task" in task_titles
    assert "Second Task" in task_titles
    assert "Third Task" in task_titles
    
    # And each task includes basic information
    for task in result:
        assert hasattr(task, 'id')
        assert hasattr(task, 'title')
        assert hasattr(task, 'description')
        assert hasattr(task, 'column')
        assert hasattr(task, 'chat_id')
        # Notes and documents should not be included in list view
        assert not hasattr(task, 'notes')
        assert not hasattr(task, 'documents')


@pytest.mark.asyncio
async def test_list_tasks_empty_list(session):
    # Given an authenticated user exists but no tasks exist
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

    # When they request the task list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    result = await list_tasks(token=token, db_session=session)

    # Then the system returns an empty list
    assert len(result) == 0
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_tasks_not_auth(session):
    # Given tasks exist but invalid token
    task = Task(
        title="Unauthorized Task",
        column="To Do"
    )
    session.add(task)
    session.commit()

    # When they request task list with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await list_tasks(token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()