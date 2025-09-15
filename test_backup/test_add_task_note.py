"""
Feature: Add note to task
  As an authenticated user or agent
  I want to add a note to an existing task
  So that I can provide additional context or updates

Scenario: Successfully add note to task
  Given an authenticated user exists
  And a task exists
  When they add a note with content to the task
  Then the system creates the note successfully
  And links it to the task
  And returns the note information

Scenario: Add note to non-existent task
  Given an authenticated user exists
  When they try to add a note to a non-existent task
  Then the system returns 404 Not Found error

Scenario: Add note without authentication
  Given a task exists
  And no valid authentication token is provided
  When they try to add a note to the task
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.notes import Note, TaskNote
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import add_task_note
from apis.schemas.tasks import CreateTaskNoteRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_add_task_note_success(session):
    # Given an authenticated user exists and a task exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task for Notes",
        description="Task to receive notes",
        column="In Progress"
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

    # When they add a note with content to the task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    note_data = CreateTaskNoteRequest(
        content="This is a task note with important information"
    )
    
    result = await add_task_note(
        task_id=task.id,
        note_data=note_data,
        token=token,
        db_session=session
    )

    # Then the system creates the note successfully
    assert result.content == "This is a task note with important information"
    assert result.created_by_user_id == user.id
    assert result.id is not None
    assert result.created_at is not None
    
    # And links it to the task
    task_note_statement = select(TaskNote).where(TaskNote.task_id == task.id, TaskNote.note_id == result.id)
    task_note_link = session.exec(task_note_statement).first()
    assert task_note_link is not None
    assert task_note_link.task_id == task.id
    assert task_note_link.note_id == result.id
    
    # And stores the note in database
    note_statement = select(Note).where(Note.id == result.id)
    stored_note = session.exec(note_statement).first()
    assert stored_note is not None
    assert stored_note.content == "This is a task note with important information"


@pytest.mark.asyncio
async def test_add_task_note_task_not_found(session):
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

    # When they try to add a note to a non-existent task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    note_data = CreateTaskNoteRequest(
        content="Note for non-existent task"
    )
    
    try:
        result = await add_task_note(
            task_id="task_nonexistent",
            note_data=note_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_add_task_note_not_auth(session):
    # Given a task exists and no valid authentication token is provided
    task = Task(
        title="Unauthorized Task",
        column="To Do"
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    note_data = CreateTaskNoteRequest(
        content="Unauthorized note"
    )

    # When they try to add a note to the task
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await add_task_note(
            task_id=task.id,
            note_data=note_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()