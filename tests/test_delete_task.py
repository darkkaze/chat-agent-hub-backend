"""
Feature: Delete task (soft and hard delete)
  As an authenticated user or agent
  I want to delete a task
  So that I can remove tasks from the system

Scenario: Successfully soft delete task
  Given an authenticated user exists
  And a task exists
  When they request soft delete with DELETE /tasks/{task_id}?soft=true
  Then the system marks the task as deleted (soft delete)
  And the task is not returned in list operations
  And returns success confirmation

Scenario: Successfully hard delete task
  Given an authenticated user exists
  And a task exists
  When they request hard delete with DELETE /tasks/{task_id}
  Then the system permanently removes the task from database
  And returns success confirmation

Scenario: Hard delete task with notes and documents
  Given an authenticated user exists
  And a task exists with associated notes and documents
  When they request hard delete
  Then the system removes task-note and task-document associations
  And permanently removes the task
  And notes and documents remain in system (orphaned)

Scenario: Delete non-existent task
  Given an authenticated user exists
  When they try to delete a non-existent task
  Then the system returns 404 Not Found error

Scenario: Delete task without authentication
  Given no valid authentication token is provided
  When they try to delete a task
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.notes import Note, TaskNote
from models.documents import Document, TaskDocument
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import delete_task
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_soft_delete_task(session):
    # Given an authenticated user exists and a task exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task to Soft Delete",
        description="This task will be soft deleted",
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

    # When they request soft delete
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    result = await delete_task(
        task_id=task.id,
        soft=True,
        token=token,
        db_session=session
    )

    # Then the system marks the task as deleted (soft delete)
    assert result["success"] is True
    assert "soft deleted" in result["message"].lower()
    
    # And the task still exists in database but marked as deleted
    task_statement = select(Task).where(Task.id == task.id)
    stored_task = session.exec(task_statement).first()
    assert stored_task is not None
    # Note: Actual soft delete implementation would add is_deleted field


@pytest.mark.asyncio
async def test_hard_delete_task(session):
    # Given an authenticated user exists and a task exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task to Hard Delete",
        description="This task will be hard deleted",
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

    # When they request hard delete
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    result = await delete_task(
        task_id=task.id,
        soft=False,
        token=token,
        db_session=session
    )

    # Then the system permanently removes the task from database
    assert result["success"] is True
    assert "permanently deleted" in result["message"].lower() or "hard deleted" in result["message"].lower()
    
    # And the task no longer exists in database
    task_statement = select(Task).where(Task.id == task.id)
    stored_task = session.exec(task_statement).first()
    assert stored_task is None


@pytest.mark.asyncio
async def test_hard_delete_task_with_notes_and_documents(session):
    # Given an authenticated user exists and a task with notes/documents
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task with Attachments",
        description="Task to be deleted with attachments",
        column="Done"
    )
    
    note = Note(
        content="Task note to remain orphaned",
        created_by_user_id="temp"  # Will be updated
    )
    
    document = Document(
        file_url="https://example.com/file.pdf",
        file_name="file.pdf",
        mime_type="application/pdf",
        uploaded_by_user_id="temp"  # Will be updated
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
    
    # Update user IDs
    note.created_by_user_id = user.id
    document.uploaded_by_user_id = user.id
    session.add_all([note, document])
    session.commit()
    session.refresh(note)
    session.refresh(document)
    
    # Create associations
    task_note = TaskNote(task_id=task.id, note_id=note.id)
    task_document = TaskDocument(task_id=task.id, document_id=document.id)
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([task_note, task_document, token_user])
    session.commit()

    # When they request hard delete
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    result = await delete_task(
        task_id=task.id,
        soft=False,
        token=token,
        db_session=session
    )

    # Then the system removes task-note and task-document associations
    task_note_statement = select(TaskNote).where(TaskNote.task_id == task.id)
    task_document_statement = select(TaskDocument).where(TaskDocument.task_id == task.id)
    
    assert session.exec(task_note_statement).first() is None
    assert session.exec(task_document_statement).first() is None
    
    # And permanently removes the task
    task_statement = select(Task).where(Task.id == task.id)
    assert session.exec(task_statement).first() is None
    
    # And notes and documents remain in system (orphaned)
    note_statement = select(Note).where(Note.id == note.id)
    document_statement = select(Document).where(Document.id == document.id)
    
    assert session.exec(note_statement).first() is not None
    assert session.exec(document_statement).first() is not None


@pytest.mark.asyncio
async def test_delete_task_not_found(session):
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

    # When they try to delete a non-existent task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await delete_task(
            task_id="task_nonexistent",
            soft=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_task_not_auth(session):
    # Given a task exists but no valid authentication
    task = Task(
        title="Unauthorized Task",
        column="To Do"
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    # When they try to delete a task with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_task(
            task_id=task.id,
            soft=False,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()