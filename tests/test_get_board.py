"""
Feature: Get board with all columns and tasks
  As an authenticated user or agent
  I want to retrieve a specific board with its details
  So that I can see the board structure and tasks

Scenario: Successfully get existing board
  Given a valid authentication token exists
  And a board exists in the system
  When they request board details with GET /boards/{board_id}
  Then the system returns the board information
  And includes id, name, columns

Scenario: Get non-existent board
  Given a valid authentication token exists
  When they request details for a non-existent board
  Then the system returns 404 Not Found error

Scenario: Get board without authentication
  Given no valid authentication token is provided
  When they request board details with GET /boards/{board_id}
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Token, TokenUser, UserRole
from models.boards import Board
from models.channels import Channel  # Need to import to create tables
from database import get_session
from apis.boards import get_board
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_get_board_success(session):
    # Given a valid token and an existing board
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    board = Board(
        name="Project Board",
        columns=["Backlog", "In Progress", "Testing", "Done"]
    )
    
    token = Token(
        access_token="valid_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([user, board, token])
    session.commit()
    session.refresh(user)
    session.refresh(board)
    session.refresh(token)
    
    # Link token to user
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # When they request board details
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer valid_token", db_session=session)
    result = await get_board(board_id=board.id, token=token, db_session=session)

    # Then the system returns the board information
    assert result.id == board.id
    assert result.name == "Project Board"
    assert result.columns == ["Backlog", "In Progress", "Testing", "Done"]


@pytest.mark.asyncio
async def test_get_board_not_found(session):
    # Given a valid token but non-existent board
    user = User(
        username="user",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="valid_token",
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

    # When they request details for non-existent board
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer valid_token", db_session=session)
    
    try:
        result = await get_board(board_id="board_nonexistent", token=token, db_session=session)
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_get_board_not_auth(session):
    # Given a board exists but invalid token
    board = Board(
        name="Unauthorized Board",
        columns=["Column1", "Column2"]
    )
    session.add(board)
    session.commit()
    session.refresh(board)

    # When they request board details with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await get_board(board_id=board.id, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()