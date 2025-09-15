"""
Feature: Create a new board
  As an admin user or agent
  I want to create a new Kanban board
  So that I can organize work with columns

Scenario: Admin successfully creates board
  Given an admin user is authenticated
  When they create a board with name and columns
  Then the system creates the board successfully
  And returns the board information
  And stores the board in the database

Scenario: Agent successfully creates board
  Given an agent is authenticated
  When they create a board with name and columns
  Then the system creates the board successfully
  And returns the board information

Scenario: Create board with minimal data
  Given an admin user is authenticated
  When they create a board with only name (no columns)
  Then the system creates the board successfully
  And board has empty columns list

Scenario: Member user tries to create board
  Given a member user is authenticated
  When they try to create a board
  Then the system returns 403 Forbidden error
  And does not create the board

Scenario: Create board without authentication
  Given no valid authentication token is provided
  When they try to create a board
  Then the system returns 401 Unauthorized error
"""

import pytest
from sqlmodel import create_engine, Session, SQLModel, select
from models.auth import User, Agent, Token, TokenUser, TokenAgent, UserRole
from models.boards import Board
from models.channels import Channel  # Need to import to create tables
from database import get_session
from apis.boards import create_board
from apis.schemas.boards import CreateBoardRequest
from datetime import datetime, timezone, timedelta


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_create_board_admin_success(session):
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
    
    # Link token to admin user
    token_user = TokenUser(token_id=token.id, user_id=admin_user.id)
    session.add(token_user)
    session.commit()

    # When they create a board with name and columns
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    board_data = CreateBoardRequest(
        name="Development Workflow",
        columns=["Backlog", "In Progress", "Code Review", "Testing", "Done"]
    )
    
    result = await create_board(
        board_data=board_data,
        token=token,
        db_session=session
    )

    # Then the system creates the board successfully
    assert result.name == "Development Workflow"
    assert result.columns == ["Backlog", "In Progress", "Code Review", "Testing", "Done"]
    assert result.id is not None
    
    # And stores the board in the database
    board_statement = select(Board).where(Board.id == result.id)
    stored_board = session.exec(board_statement).first()
    assert stored_board is not None
    assert stored_board.name == "Development Workflow"
    assert stored_board.columns == ["Backlog", "In Progress", "Code Review", "Testing", "Done"]


@pytest.mark.asyncio
async def test_create_board_agent_success(session):
    # Given an agent is authenticated
    agent = Agent(
        name="Board Creator Agent",
        webhook_url="https://agent.example.com/callback"
    )
    
    token = Token(
        access_token="agent_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([agent, token])
    session.commit()
    session.refresh(agent)
    session.refresh(token)
    
    # Link token to agent
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # When they create a board with name and columns
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer agent_token", db_session=session)
    
    board_data = CreateBoardRequest(
        name="Agent Created Board",
        columns=["New", "Processing", "Completed"]
    )
    
    result = await create_board(
        board_data=board_data,
        token=token,
        db_session=session
    )

    # Then the system creates the board successfully
    assert result.name == "Agent Created Board"
    assert result.columns == ["New", "Processing", "Completed"]
    assert result.id is not None


@pytest.mark.asyncio
async def test_create_board_minimal_data(session):
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

    # When they create a board with only name (no columns)
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer admin_token", db_session=session)
    
    board_data = CreateBoardRequest(
        name="Minimal Board"
        # columns defaults to empty list
    )
    
    result = await create_board(
        board_data=board_data,
        token=token,
        db_session=session
    )

    # Then the system creates the board successfully
    assert result.name == "Minimal Board"
    # And board has empty columns list
    assert result.columns == []
    assert result.id is not None


@pytest.mark.asyncio
async def test_create_board_member_forbidden(session):
    # Given a member user is authenticated
    member_user = User(
        username="member",
        hashed_password="hashed_secret",
        role=UserRole.MEMBER
    )
    
    token = Token(
        access_token="member_token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_revoked=False
    )
    
    session.add_all([member_user, token])
    session.commit()
    session.refresh(member_user)
    session.refresh(token)
    
    token_user = TokenUser(token_id=token.id, user_id=member_user.id)
    session.add(token_user)
    session.commit()

    # When they try to create a board
    from helpers.auth import get_auth_token
    token = await get_auth_token(authorization="Bearer member_token", db_session=session)
    
    board_data = CreateBoardRequest(
        name="Unauthorized Board",
        columns=["Column1"]
    )

    try:
        result = await create_board(
            board_data=board_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised a forbidden error"
    except Exception as e:
        # Then the system returns 403 Forbidden error
        assert "403" in str(e) or "forbidden" in str(e).lower() or "admin or agent access required" in str(e).lower()
        
        # And does not create the board
        board_statement = select(Board).where(Board.name == "Unauthorized Board")
        boards = session.exec(board_statement).all()
        assert len(boards) == 0


@pytest.mark.asyncio
async def test_create_board_not_auth(session):
    # Given no valid authentication token is provided
    board_data = CreateBoardRequest(
        name="Unauthorized Board",
        columns=["Column1"]
    )

    # When they try to create a board
    from helpers.auth import get_auth_token
    try:
        token = await get_auth_token(authorization="Bearer invalid_token", db_session=session)
        result = await create_board(
            board_data=board_data,
            token=token,
            db_session=session
        )
        assert False, "Should have raised an authentication error"
    except Exception as e:
        # Then the system returns 401 Unauthorized error
        assert "401" in str(e) or "unauthorized" in str(e).lower()