"""
Feature: Delete task note (physical delete only)
  As an authenticated user or agent
  I want to permanently delete a note from a task
  So that I can remove outdated or incorrect information

Scenario: Successfully delete task note
  Given an authenticated user exists
  And a task exists with an associated note
  When they request to delete the note from the task
  Then the system removes the task-note association
  And permanently deletes the note from the database
  And returns success confirmation

Scenario: Delete note from task that doesn't have the note
  Given an authenticated user exists
  And a task exists
  And a note exists but is not associated with the task
  When they try to delete the note from the task
  Then the system returns 404 Not Found error

Scenario: Delete non-existent note from task
  Given an authenticated user exists
  And a task exists
  When they try to delete a non-existent note from the task
  Then the system returns 404 Not Found error

Scenario: Delete note from non-existent task
  Given an authenticated user exists
  When they try to delete a note from a non-existent task
  Then the system returns 404 Not Found error

Scenario: Delete task note without authentication
  Given a task exists with an associated note
  And no valid authentication token is provided
  When they try to delete the note from the task
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.notes import Note, TaskNote
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import delete_task_note
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_task_note_success(session):
    # Given an authenticated user exists and a task with associated note
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task with Note",
        description="Task that has a note to be deleted",
        column="In Progress"
    )
    
    note = Note(
        content="Note to be deleted",
        created_by_user_id="temp"  # Will be updated
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
    
    # Update note with real user ID
    note.created_by_user_id = user.id
    session.add(note)
    session.commit()
    session.refresh(note)
    
    # Create task-note association
    task_note = TaskNote(task_id=task.id, note_id=note.id)
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([task_note, token_user])
    session.commit()

    # When they request to delete the note from the task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    result = await delete_task_note(
        task_id=task.id,
        note_id=note.id,
        token=token,
        db_session=session
    )

    # Then the system removes the task-note association
    task_note_statement = select(TaskNote).where(TaskNote.task_id == task.id, TaskNote.note_id == note.id)
    task_note_link = session.exec(task_note_statement).first()
    assert task_note_link is None
    
    # And permanently deletes the note from the database
    note_statement = select(Note).where(Note.id == note.id)
    stored_note = session.exec(note_statement).first()
    assert stored_note is None
    
    # And returns success confirmation
    assert result["success"] is True
    assert "deleted" in result["message"].lower()


@pytest.mark.asyncio
async def test_delete_task_note_not_associated(session):
    # Given an authenticated user exists and a task exists and a note exists but not associated
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task without Note",
        column="To Do"
    )
    
    note = Note(
        content="Unassociated note",
        created_by_user_id="temp"  # Will be updated
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
    
    # Update note with real user ID
    note.created_by_user_id = user.id
    session.add(note)
    session.commit()
    session.refresh(note)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they try to delete the note from the task (not associated)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await delete_task_note(
            task_id=task.id,
            note_id=note.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_task_note_nonexistent_note(session):
    # Given an authenticated user exists and a task exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task",
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

    # When they try to delete a non-existent note from the task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await delete_task_note(
            task_id=task.id,
            note_id="note_nonexistent",
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_task_note_nonexistent_task(session):
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

    # When they try to delete a note from a non-existent task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await delete_task_note(
            task_id="task_nonexistent",
            note_id="note_123",
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_task_note_not_auth(session):
    # Given a task exists with an associated note and no valid authentication
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task with Note",
        column="To Do"
    )
    
    session.add_all([user, task])
    session.commit()
    session.refresh(user)
    session.refresh(task)
    
    note = Note(
        content="Note to be deleted",
        created_by_user_id=user.id
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    
    task_note = TaskNote(task_id=task.id, note_id=note.id)
    session.add(task_note)
    session.commit()

    # When they try to delete the note from the task with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_task_note(
            task_id=task.id,
            note_id=note.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()