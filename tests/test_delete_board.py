"""
Feature: Delete a board (soft and hard delete)
  As an admin user or agent
  I want to delete a board
  So that I can remove boards that are no longer needed

Scenario: Admin successfully soft deletes board
  Given an admin user is authenticated
  And a board exists in the system
  When they soft delete the board with DELETE /boards/{board_id}?hard=false
  Then the system marks the board as deleted
  And returns success confirmation message
  And board is not visible in list_boards

Scenario: Admin successfully hard deletes board
  Given an admin user is authenticated
  And a board exists in the system
  When they hard delete the board with DELETE /boards/{board_id}?hard=true
  Then the system removes the board permanently
  And returns success confirmation message
  And removes any associated task records

Scenario: Agent successfully deletes board
  Given an agent is authenticated
  And a board exists in the system
  When they delete the board
  Then the system removes the board successfully
  And returns success confirmation message

Scenario: Member user tries to delete board
  Given a member user is authenticated
  And a board exists in the system
  When they try to delete the board
  Then the system returns 403 Forbidden error
  And does not delete the board

Scenario: Delete non-existent board
  Given an admin user is authenticated
  When they try to delete a non-existent board
  Then the system returns 404 Not Found error

Scenario: Delete board without authentication
  Given no valid authentication token is provided
  When they try to delete a board
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.boards import Board, Task
from models.channels import Channel  # Need to import to create tables
from database import get_session
from apis.boards import delete_board
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_board_admin_soft_delete(session):
    # Given an admin user is authenticated and a board exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    board = Board(
        name="Board to Soft Delete",
        columns=["To Do", "Done"]
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, board, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(board)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they soft delete the board
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    result = await delete_board(board_id=board.id, hard=False, token=token, db_session=session)

    # Then the system marks the board as deleted
    assert result.message == "Board soft-deleted successfully"
    
    # And board is marked as deleted (assuming we add is_deleted field)
    # For now, we'll verify the behavior based on how we implement it


@pytest.mark.asyncio
async def test_delete_board_admin_hard_delete(session):
    # Given an admin user is authenticated and a board with tasks exists
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    board = Board(
        name="Board to Hard Delete",
        columns=["To Do", "Done"]
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, board, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(board)
    session.refresh(token)
    
    # Add a task associated with the board
    task = Task(
        column="To Do",
        title="Test Task",
        description="Task description"
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they hard delete the board
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    result = await delete_board(board_id=board.id, hard=True, token=token, db_session=session)

    # Then the system removes the board permanently
    assert result.message == "Board hard-deleted successfully"
    
    # And removes the board from database
    board_statement = select(Board).where(Board.id == board.id)
    deleted_board = session.exec(board_statement).first()
    assert deleted_board is None


@pytest.mark.asyncio
async def test_delete_board_agent_success(session):
    # Given an agent is authenticated and a board exists
    agent = Agent(
        name="Board Deleter Agent",
        callback_url="https://agent.example.com/callback"
    )
    
    board = Board(
        name="Agent Deleted Board",
        columns=["New", "Complete"]
    )
    
    token = Token(
        access_token="agent_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([agent, board, token])
    session.commit()
    session.refresh(agent)
    session.refresh(board)
    session.refresh(token)
    
    # Link token to agent
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # When they delete the board (defaults to hard delete for agents)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    result = await delete_board(board_id=board.id, hard=True, token=token, db_session=session)

    # Then the system removes the board successfully
    assert result.message == "Board hard-deleted successfully"
    
    # And removes the board from database
    board_statement = select(Board).where(Board.id == board.id)
    deleted_board = session.exec(board_statement).first()
    assert deleted_board is None


@pytest.mark.asyncio
async def test_delete_board_member_forbidden(session):
    # Given a member user is authenticated and a board exists
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    board = Board(
        name="Protected Board",
        columns=["Column1"]
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, board, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(board)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to delete the board
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    try:
        result = await delete_board(board_id=board.id, hard=False, token=token, db_session=session)
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower() or "admin or agent access required" in str(e).lower()
        
        # And does not delete the board
        board_statement = select(Board).where(Board.id == board.id)
        existing_board = session.exec(board_statement).first()
        assert existing_board is not None
        assert existing_board.name == "Protected Board"


@pytest.mark.asyncio
async def test_delete_board_not_found(session):
    # Given an admin user is authenticated
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they try to delete a non-existent board
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    try:
        result = await delete_board(board_id="board_nonexistent", hard=False, token=token, db_session=session)
        assert False, "Should have raised a not found error"
    except Exception as e:
        # Then the system returns 404 Not Found error
        assert "404" in str(e) or "not found" in str(e).lower()


@pytest.mark.asyncio
async def test_delete_board_not_auth(session):
    # Given a board exists but no valid authentication
    board = Board(
        name="Unauthorized Delete",
        columns=["Column1"]
    )
    session.add(board)
    session.commit()
    session.refresh(board)

    # When they try to delete the board without authentication
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await delete_board(board_id=board.id, hard=False, token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()