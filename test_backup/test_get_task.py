"""
Feature: Get task with notes and documents
  As an authenticated user or agent
  I want to retrieve a specific task with its details
  So that I can see the task information, notes, and documents

Scenario: Successfully get existing task with notes and documents
  Given an authenticated user exists
  And a task exists with associated notes and documents
  When they request task details with GET /tasks/{task_id}
  Then the system returns the task information
  And includes id, title, description, column, chat_id
  And includes list of associated notes
  And includes list of associated documents

Scenario: Get task with no notes or documents
  Given an authenticated user exists
  And a task exists with no associated notes or documents
  When they request task details
  Then the system returns the task information
  And notes list is empty
  And documents list is empty

Scenario: Get non-existent task
  Given an authenticated user exists
  When they request details for a non-existent task
  Then the system returns 404 Not Found error

Scenario: Get task without authentication
  Given no valid authentication token is provided
  When they request task details
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.notes import Note, TaskNote
from models.documents import Document, TaskDocument
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import get_task
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_get_task_with_notes_and_documents(session):
    # Given an authenticated user exists and a task with notes/documents
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task with Attachments",
        description="This task has notes and documents",
        column="In Progress"
    )
    
    note = Note(
        content="This is a task note",
        created_by_user_id="user_123"  # We'll set this properly after user creation
    )
    
    document = Document(
        file_url="https://example.com/document.pdf",
        file_name="document.pdf",
        mime_type="application/pdf",
        uploaded_by_user_id="user_123"  # We'll set this properly after user creation
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
    
    # Update the user IDs with actual user ID
    note.created_by_user_id = user.id
    document.uploaded_by_user_id = user.id
    session.add_all([note, document])
    session.commit()
    session.refresh(note)
    session.refresh(document)
    
    # Link note and document to task
    task_note = TaskNote(task_id=task.id, note_id=note.id)
    task_document = TaskDocument(task_id=task.id, document_id=document.id)
    
    # Link token to user
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([task_note, task_document, token_user])
    session.commit()

    # When they request task details
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    result = await get_task(task_id=task.id, token=token, db_session=session)

    # Then the system returns the task information
    assert result.id == task.id
    assert result.title == "Task with Attachments"
    assert result.description == "This task has notes and documents"
    assert result.column == "In Progress"
    assert result.chat_id is None
    
    # And includes list of associated notes
    assert len(result.notes) == 1
    assert result.notes[0].content == "This is a task note"
    assert result.notes[0].created_by_user_id == user.id
    
    # And includes list of associated documents
    assert len(result.documents) == 1
    assert result.documents[0].file_name == "document.pdf"
    assert result.documents[0].file_url == "https://example.com/document.pdf"
    assert result.documents[0].mime_type == "application/pdf"


@pytest.mark.asyncio
async def test_get_task_no_notes_or_documents(session):
    # Given an authenticated user exists and a task with no notes/documents
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Simple Task",
        description="Task without attachments",
        column="Done"
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

    # When they request task details
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    result = await get_task(task_id=task.id, token=token, db_session=session)

    # Then the system returns the task information
    assert result.id == task.id
    assert result.title == "Simple Task"
    # And notes list is empty
    assert len(result.notes) == 0
    # And documents list is empty
    assert len(result.documents) == 0


@pytest.mark.asyncio
async def test_get_task_not_found(session):
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

    # When they request details for a non-existent task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await get_task(task_id="task_nonexistent", token=token, db_session=session)
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_get_task_not_auth(session):
    # Given a task exists but no valid authentication
    task = Task(
        title="Unauthorized Task",
        column="To Do"
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    # When they request task details with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await get_task(task_id=task.id, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()