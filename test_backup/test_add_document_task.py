"""
Feature: Attach document to task
  As an authenticated user or agent
  I want to attach a document to an existing task
  So that I can associate files with work items

Scenario: Successfully attach document to task
  Given an authenticated user exists
  And a task exists
  When they attach a document with file details to the task
  Then the system creates the document record successfully
  And links it to the task
  And returns the document information

Scenario: Attach document to non-existent task
  Given an authenticated user exists
  When they try to attach a document to a non-existent task
  Then the system returns 404 Not Found error

Scenario: Attach document without authentication
  Given a task exists
  And no valid authentication token is provided
  When they try to attach a document to the task
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Task
from models.documents import Document, TaskDocument
from models.channels import Channel  # Need for foreign keys
from database import get_session
from apis.tasks import add_document_task
from apis.schemas.tasks import CreateTaskDocumentRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_add_document_task_success(session):
    # Given an authenticated user exists and a task exists
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    task = Task(
        title="Task for Documents",
        description="Task to receive documents",
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

    # When they attach a document with file details to the task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    document_data = CreateTaskDocumentRequest(
        file_url="https://example.com/project_spec.pdf",
        file_name="project_spec.pdf",
        mime_type="application/pdf"
    )
    
    result = await add_document_task(
        task_id=task.id,
        document_data=document_data,
        token=token,
        db_session=session
    )

    # Then the system creates the document record successfully
    assert result.file_url == "https://example.com/project_spec.pdf"
    assert result.file_name == "project_spec.pdf"
    assert result.mime_type == "application/pdf"
    assert result.uploaded_by_user_id == user.id
    assert result.id is not None
    assert result.uploaded_at is not None
    
    # And links it to the task
    task_document_statement = select(TaskDocument).where(TaskDocument.task_id == task.id, TaskDocument.document_id == result.id)
    task_document_link = session.exec(task_document_statement).first()
    assert task_document_link is not None
    assert task_document_link.task_id == task.id
    assert task_document_link.document_id == result.id
    
    # And stores the document in database
    document_statement = select(Document).where(Document.id == result.id)
    stored_document = session.exec(document_statement).first()
    assert stored_document is not None
    assert stored_document.file_name == "project_spec.pdf"


@pytest.mark.asyncio
async def test_add_document_task_task_not_found(session):
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

    # When they try to attach a document to a non-existent task
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer user_token", db_session=session)
    
    document_data = CreateTaskDocumentRequest(
        file_url="https://example.com/file.pdf",
        file_name="file.pdf",
        mime_type="application/pdf"
    )
    
    try:
        result = await add_document_task(
            task_id="task_nonexistent",
            document_data=document_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_add_document_task_not_auth(session):
    # Given a task exists and no valid authentication token is provided
    task = Task(
        title="Unauthorized Task",
        column="To Do"
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    document_data = CreateTaskDocumentRequest(
        file_url="https://example.com/unauthorized.pdf",
        file_name="unauthorized.pdf",
        mime_type="application/pdf"
    )

    # When they try to attach a document to the task
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await add_document_task(
            task_id=task.id,
            document_data=document_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()