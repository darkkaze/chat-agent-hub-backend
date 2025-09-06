# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Architecture

This is a FastAPI backend for an Agent Hub system that manages multi-platform chat conversations, external AI agents, and Kanban-style task management.

### Core Components

**FastAPI Application (`main.py`)**

- Main application entry point that includes all API routers
- Uses dependency injection for database sessions

**Database Layer (`database.py`)**

- SQLModel with SQLite backend (`agent_hub.db`)
- Dependency injection pattern: `session: Session = Depends(get_session)`
- Engine configured with echo=True for development

**Models (`models/`)**

- Custom ID generation using `id_generator(prefix, n)` from `models/helper.py`
- All models use format: `{prefix}_{10_random_chars}` (e.g., `user_a3b5k9m2x7`)
- Safe character set excludes visually confusing chars (0, O, 1, l, I)

### Key Models Structure

**User Management:**

- `User`: Internal operators with optional email/phone, roles (ADMIN/MEMBER)
- `Token`: JWT session management with access/refresh tokens
- `UserChannelPermission`: Links MEMBER users to accessible channels

**Communication:**

- `Channel`: Platform connections (WhatsApp, Telegram, Instagram) with JSON credentials
- `Chat`: Conversations with optional external_id and assigned users
- `Message`: Individual messages with sender_type (CONTACT/USER/AGENT) and metadata

**External Integration:**

- `Agent`: External AI services with callback_url and fire_and_forget mode

**Task Management:**

- `Board`: Kanban boards with column arrays
- `Task`: Work units linkable to chats

**File Management:**

- `Document`/`Note`: Core entities without ownership context
- Junction tables: `ChatDocument`, `TaskDocument`, `ChatNote`, `TaskNote`

### API Structure (`apis/`)

Each module uses `APIRouter` with appropriate prefixes and tags:

- `auth.py`: Authentication (`/auth`)
- `users.py`: User management (`/users`)
- `channels.py`: Channel operations (`/channels`)
- `chats.py`: Chat and messaging (`/chats`)
- `agents.py`: External agent management (`/agents`)
- `webhooks.py`: Platform webhooks (`/webhooks`)
- `boards.py`: Kanban boards (`/boards`)
- `tasks.py`: Task operations (`/tasks`)

### Background Tasks (`tasks/`, `worker.py`)

**Celery Configuration:**

- Redis broker/backend on localhost:6379
- Worker entry point: `worker.py`
- Task modules in `tasks/` directory
- `agent_callback` task for processing agent responses

## Development Commands

**Start FastAPI server:**

```bash
fastapi dev main.py
```

**Start Celery worker:**

```bash
celery -A worker worker --loglevel=info
```

**Database:**

- Uses SQLModel with dependency injection
- No automatic table creation - handle migrations separately
- Import `get_session` from `database.py` for endpoints

## Key Patterns

**Logging:**

- Import logger from settings: `from settings import logger`
- Use structured logging: `logger.info("Processing chat", extra={"chat_id": chat_id})`
- Logs written to stdout (captured by system in production)
- Third-party loggers (uvicorn, sqlalchemy) set to WARNING level

**Model Relationships:**

- Foreign keys reference table names (lowercase class names)
- Junction tables for many-to-many relationships
- Optional fields use `Optional[type] = Field(default=None)`

**API Endpoints:**

- Async functions with descriptive docstrings
- Use `Depends(get_session)` for database access
- Path parameters typed as `str` for custom IDs

**Unit Testing:**

Test APIs rather than models directly - this indirectly tests models and other functions.
Use SQLite in memory for test fixtures.

**Test Structure:**

```
tests/
    test_get_current_user.py
    test_create_user.py
    test_list_channels.py
    test_create_channel.py
```

File names match the API function being tested.

**Test Setup:**

```python
import pytest
from sqlmodel import create_engine, Session, SQLModel
from models import User, Agent
from database import get_session
from apis.users import get_current_user

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

def test_get_current_user(session):
    # Create a user in the test session
    user = User(username="foobar", email="foo@bar.com")
    session.add(user)
    session.commit()
    session.refresh(user)

    # Call the function directly
    result = get_current_user(session=session, user_id=user.id)
    assert result.username == "foobar"
    assert result.email == "foo@bar.com"
```
