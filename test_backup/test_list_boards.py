"""
Feature: List all boards
  As an authenticated user or agent
  I want to retrieve a list of all boards
  So that I can see available Kanban boards

Scenario: Admin successfully lists all boards
  Given an admin user is authenticated
  And there are boards in the system
  When they request the board list with GET /boards
  Then the system returns all boards
  And each board includes id, name, columns

Scenario: Member successfully lists all boards
  Given a member user is authenticated
  And there are boards in the system
  When they request the board list with GET /boards
  Then the system returns all boards
  And each board includes id, name, columns

Scenario: Agent successfully lists all boards
  Given an agent is authenticated
  And there are boards in the system
  When they request the board list with GET /boards
  Then the system returns all boards

Scenario: List boards when none exist
  Given a valid authentication token exists
  And no boards exist in the system
  When they request the board list with GET /boards
  Then the system returns an empty list

Scenario: List boards without authentication
  Given no valid authentication token is provided
  When they request the board list with GET /boards
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.boards import Board
from models.channels import Channel  # Need to import to create tables
from database import get_session
from apis.boards import list_boards
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_list_boards_admin_success(session):
    # Given an admin user is authenticated and boards exist
    admin_user = User(
        username="admin",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )
    
    board1 = Board(
        name="Development Board",
        columns=["Backlog", "In Progress", "Review", "Done"]
    )
    
    board2 = Board(
        name="Marketing Board", 
        columns=["Ideas", "Planning", "Execution", "Complete"]
    )
    
    token = Token(
        access_token="admin_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([admin_user, board1, board2, token])
    session.commit()
    session.refresh(admin_user)
    session.refresh(board1)
    session.refresh(board2)
    session.refresh(token)
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they request the board list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    result = await list_boards(token=token, db_session=session)

    # Then the system returns all boards
    assert len(result) == 2
    board_names = [board.name for board in result]
    assert "Development Board" in board_names
    assert "Marketing Board" in board_names
    
    # And each board includes id, name, columns
    for board in result:
        assert hasattr(board, 'id')
        assert hasattr(board, 'name')
        assert hasattr(board, 'columns')
        assert isinstance(board.columns, list)


@pytest.mark.asyncio
async def test_list_boards_member_success(session):
    # Given a member user is authenticated and boards exist
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    board = Board(
        name="Team Board",
        columns=["To Do", "Doing", "Done"]
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

    # When they request the board list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    result = await list_boards(token=token, db_session=session)

    # Then the system returns all boards
    assert len(result) == 1
    assert result[0].name == "Team Board"
    assert result[0].columns == ["To Do", "Doing", "Done"]


@pytest.mark.asyncio
async def test_list_boards_agent_success(session):
    # Given an agent is authenticated and boards exist
    agent = Agent(
        name="Board Reader Agent",
        webhook_url="https://agent.example.com/callback"
    )
    
    board = Board(
        name="Agent Board",
        columns=["New", "Processing", "Completed"]
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

    # When they request the board list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    result = await list_boards(token=token, db_session=session)

    # Then the system returns all boards
    assert len(result) == 1
    assert result[0].name == "Agent Board"


@pytest.mark.asyncio
async def test_list_boards_empty_list(session):
    # Given a valid token but no boards exist
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

    # When they request the board list
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    result = await list_boards(token=token, db_session=session)

    # Then the system returns an empty list
    assert len(result) == 0
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_boards_not_auth(session):
    # Given boards exist but invalid token
    board = Board(
        name="Unauthorized Board",
        columns=["Column1"]
    )
    session.add(board)
    session.commit()

    # When they request board list with invalid token
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await list_boards(token=token, db_session=session)
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()