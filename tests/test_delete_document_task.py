"""
Feature: Delete task document (physical delete only)
  As an authenticated user or agent
  I want to permanently delete a document from a task
  So that I can remove outdated or incorrect files

Scenario: Successfully delete task document
  Given an authenticated user exists
  And a task exists with an associated document
  When they request to delete the document from the task
  Then the system removes the task-document association
  And permanently deletes the document from the database
  And returns success confirmation

Scenario: Delete document from task that doesn't have the document
  Given an authenticated user exists
  And a task exists
  And a document exists but is not associated with the task
  When they try to delete the document from the task
  Then the system returns 404 Not Found error

Scenario: Delete non-existent document from task
  Given an authenticated user exists
  And a task exists
  When they try to delete a non-existent document from the task
  Then the system returns 404 Not Found error

Scenario: Delete document from non-existent task
  Given an authenticated user exists
  When they try to delete a document from a non-existent task
  Then the system returns 404 Not Found error

Scenario: Delete task document without authentication
  Given a task exists with an associated document
  And no valid authentication token is provided
  When they try to delete the document from the task
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.documents import Document, TaskDocument
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import delete_document_task
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_document_task_success(session):
    # Given an authenticated user exists and a task with associated document
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task with Document",
        description="Task that has a document to be deleted",
        column="In Progress"
    )
    
    document = Document(
        file_url="https://example.com/to_delete.pdf",
        file_name="to_delete.pdf",
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
    
    # Update document with real user ID
    document.uploaded_by_user_id = user.id
    session.add(document)
    session.commit()
    session.refresh(document)
    
    # Create task-document association
    task_document = TaskDocument(task_id=task.id, document_id=document.id)
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    
    session.add_all([task_document, token_user])
    session.commit()

    # When they request to delete the document from the task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    result = await delete_document_task(
        task_id=task.id,
        document_id=document.id,
        token=token,
        db_session=session
    )

    # Then the system removes the task-document association
    task_document_statement = select(TaskDocument).where(TaskDocument.task_id == task.id, TaskDocument.document_id == document.id)
    task_document_link = session.exec(task_document_statement).first()
    assert task_document_link is None
    
    # And permanently deletes the document from the database
    document_statement = select(Document).where(Document.id == document.id)
    stored_document = session.exec(document_statement).first()
    assert stored_document is None
    
    # And returns success confirmation
    assert result["success"] is True
    assert "deleted" in result["message"].lower()


@pytest.mark.asyncio
async def test_delete_document_task_not_associated(session):
    # Given an authenticated user exists and a task exists and a document exists but not associated
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task without Document",
        column="To Do"
    )
    
    document = Document(
        file_url="https://example.com/unassociated.pdf",
        file_name="unassociated.pdf",
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
    
    # Update document with real user ID
    document.uploaded_by_user_id = user.id
    session.add(document)
    session.commit()
    session.refresh(document)
    
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they try to delete the document from the task (not associated)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await delete_document_task(
            task_id=task.id,
            document_id=document.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_document_task_nonexistent_document(session):
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

    # When they try to delete a non-existent document from the task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await delete_document_task(
            task_id=task.id,
            document_id="document_nonexistent",
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_document_task_nonexistent_task(session):
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

    # When they try to delete a document from a non-existent task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    try:
        result = await delete_document_task(
            task_id="task_nonexistent",
            document_id="document_123",
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_document_task_not_auth(session):
    # Given a task exists with an associated document and no valid authentication
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task with Document",
        column="To Do"
    )
    
    session.add_all([user, task])
    session.commit()
    session.refresh(user)
    session.refresh(task)
    
    document = Document(
        file_url="https://example.com/unauthorized.pdf",
        file_name="unauthorized.pdf",
        mime_type="application/pdf",
        uploaded_by_user_id=user.id
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    
    task_document = TaskDocument(task_id=task.id, document_id=document.id)
    session.add(task_document)
    session.commit()

    # When they try to delete the document from the task with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_document_task(
            task_id=task.id,
            document_id=document.id,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()