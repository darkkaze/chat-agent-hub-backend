# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Architecture

FastAPI backend for Agent Hub system that manages multi-platform chat conversations, external AI agents, and real-time notifications.

### Core Components

**FastAPI Application (`main.py`)**
- Main application entry point with all API routers
- WebSocket support for real-time notifications

**Database Layer (`database.py`)**
- SQLModel with SQLite backend (`agent_hub.db`)
- Redis for Celery broker/backend
- Dependency injection: `session: Session = Depends(get_session)`

**Models (`models/`)**
- Custom ID generation: `{prefix}_{10_random_chars}` using `id_generator()`
- Authentication models with token relationships (`TokenUser`, `TokenAgent`)
- Platform integrations and messaging models

### Key Models

**Authentication:**
- `User`: Internal operators (ADMIN/MEMBER roles)
- `Agent`: External AI services with webhook endpoints
- `Token`: Session management with automatic generation for agents

**Communication:**
- `Channel`: Platform connections (WhatsApp Twilio, Telegram, etc.)
- `Chat`: Conversations with auto-agent assignment
- `Message`: Messages with sender detection (CONTACT/USER/AGENT)
- `ChatAgent`: Links agents to specific conversations

**Real-time WebSocket (`ws_service/`):**
- WebSocket connection manager for real-time notifications
- Notifications triggered from:
  - Webhook message processing (contact messages)
  - API message sending (agent messages)
- Broadcast system for multiple connected clients
- Agent message processing with buffer algorithms

## Development Setup

**Required Services:**

Start these services in separate terminals:

```bash
# Terminal 1: FastAPI server
source .venv/bin/activate
fastapi dev main.py

# Terminal 2: Celery worker
source .venv/bin/activate
celery -A worker worker --loglevel=info

# Terminal 3: Redis (if not running as service)
redis-server
```

**Agent Testing:**

Test agent webhooks using the ping-pong server:

```bash
# Terminal 4: Test agent server
source .venv/bin/activate
python simple_agent_pingpong.py
```

## API Structure

**Core Endpoints:**
- `/auth` - User/agent authentication and management
- `/channels/{id}/chats` - Chat operations within channels
- `/webhooks/{platform}` - Inbound platform webhooks
- `/ws` - WebSocket connections for real-time updates

**Key Features:**
- Agent token authentication with automatic generation
- Real-time WebSocket notifications from multiple sources:
  - Inbound webhooks (contact messages from platforms)
  - API calls (agent responses via `/chats/{id}/messages`)
- Platform webhook processing (WhatsApp Twilio, etc.)
- Celery background tasks for agent message processing

**WebSocket Notification Sources:**
- `webhooks/whatsapp_twilio.py`: `_notify_websocket_new_message()` for contact messages
- `apis/chats.py`: `_notify_websocket_new_message()` for agent messages
- Payload format: `{type: "new_message", chat_id, message_id, sender_type, preview, ...}`

## Testing

Test APIs directly using SQLite in-memory fixtures. Mock external dependencies.

```python
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
```
