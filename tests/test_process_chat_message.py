"""
Feature: Process chat message with buffer algorithm
  As an agent processing system
  I want to buffer messages and send them efficiently to webhooks
  So that agents receive properly batched conversation context

Scenario: Process message immediately when buffer time elapsed
  Given a chat agent exists with a buffer time
  And the last message in chat is older than buffer time
  When process_chat_message is called
  Then the system sends messages immediately to webhook

Scenario: Buffer message when recent activity detected
  Given a chat agent exists with a buffer time
  And the last message in chat is within buffer time
  When process_chat_message is called
  Then the system schedules a delayed task

Scenario: Skip processing for inactive chat agent
  Given a chat agent exists but is inactive
  When process_chat_message is called
  Then the system skips processing

Scenario: Handle webhook retry mechanism
  Given a chat agent exists and buffer time elapsed
  And the webhook returns non-success status
  When messages are sent to webhook
  Then the system retries up to 3 times with 5 second delays
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlmodel import create_engine, Session, SQLModel
from datetime import datetime, timezone, timedelta
from models.auth import User, Token, TokenUser, UserRole, Agent
from models.channels import Channel, Chat, ChatAgent, Message, PlatformType, SenderType
from tasks.agent_tasks import process_chat_message, _get_recent_messages, _send_to_agent_webhook


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="setup_data")
def setup_data_fixture(session):
    """Create test data: user, channel, chat, agent, messages."""

    # Create user
    user = User(
        username="testuser",
        hashed_password="hashed_secret",
        role=UserRole.ADMIN
    )

    # Create channel
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"phone": "+1234567890"}
    )

    # Create agent with specific buffer settings
    agent = Agent(
        name="Test Agent",
        webhook_url="https://webhook.example.com/agent",
        is_active=True,
        buffer_time_seconds=5,
        history_msg_count=10,
        recent_msg_window_minutes=60
    )

    session.add_all([user, channel, agent])
    session.commit()
    session.refresh(user)
    session.refresh(channel)
    session.refresh(agent)

    # Create chat
    chat = Chat(
        name="Test Chat",
        external_id="whatsapp:+1234567890",
        channel_id=channel.id,
        last_message_ts=datetime.now(timezone.utc)
    )

    session.add(chat)
    session.commit()
    session.refresh(chat)

    # Create chat agent relationship
    chat_agent = ChatAgent(
        chat_id=chat.id,
        agent_id=agent.id,
        active=True
    )

    session.add(chat_agent)
    session.commit()
    session.refresh(chat_agent)

    # Create some test messages
    now = datetime.now(timezone.utc)
    messages = []
    for i in range(3):
        msg = Message(
            external_id=f"msg_{i}",
            chat_id=chat.id,
            content=f"Test message {i}",
            sender_type=SenderType.CONTACT,
            timestamp=now - timedelta(minutes=i*2),
            meta_data={"test": f"msg_{i}"}
        )
        session.add(msg)
        messages.append(msg)

    session.commit()
    for msg in messages:
        session.refresh(msg)

    return {
        "user": user,
        "channel": channel,
        "agent": agent,
        "chat": chat,
        "chat_agent": chat_agent,
        "messages": messages
    }


@patch('tasks.agent_tasks.Session')
def test_get_recent_messages(mock_session_class, session, setup_data):
    """Test _get_recent_messages function."""

    # Mock Session to return our test session
    mock_session_class.return_value.__enter__ = MagicMock(return_value=session)
    mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

    chat_id = setup_data["chat"].id

    # Test getting recent messages
    messages = _get_recent_messages(
        chat_id=chat_id,
        history_msg_count=10,
        recent_msg_window_minutes=60
    )

    # Should return all 3 messages in chronological order (oldest first)
    assert len(messages) == 3
    assert messages[0].content == "Test message 2"  # Oldest
    assert messages[1].content == "Test message 1"
    assert messages[2].content == "Test message 0"  # Newest


def test_send_to_agent_webhook_success():
    """Test successful webhook call."""

    with patch('requests.post') as mock_post:
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = _send_to_agent_webhook(
            webhook_url="https://test.example.com",
            payload={"test": "data"}
        )

        assert result is True
        assert mock_post.call_count == 1


def test_send_to_agent_webhook_retry():
    """Test webhook retry mechanism."""

    with patch('requests.post') as mock_post, patch('time.sleep') as mock_sleep:
        # Mock failing responses, then success
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 500
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200

        mock_post.side_effect = [mock_response_fail, mock_response_fail, mock_response_success]

        result = _send_to_agent_webhook(
            webhook_url="https://test.example.com",
            payload={"test": "data"}
        )

        assert result is True
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries


def test_send_to_agent_webhook_all_fail():
    """Test webhook when all attempts fail."""

    with patch('requests.post') as mock_post, patch('time.sleep') as mock_sleep:
        # Mock all responses failing
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = _send_to_agent_webhook(
            webhook_url="https://test.example.com",
            payload={"test": "data"}
        )

        assert result is False
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2


@patch('tasks.agent_tasks.Session')
def test_process_chat_message_buffer_elapsed(mock_session_class, session, setup_data):
    """Test processing when buffer time has elapsed."""

    # Mock Session to return our test session
    mock_session_class.return_value.__enter__ = MagicMock(return_value=session)
    mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

    chat_agent = setup_data["chat_agent"]
    chat = setup_data["chat"]

    # Set last message time to be older than buffer (5 seconds ago + 1 second)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=6)
    chat.last_message_ts = old_time
    session.add(chat)
    session.commit()

    with patch('tasks.agent_tasks._send_to_agent_webhook', return_value=True) as mock_webhook:
        result = process_chat_message(
            chat_agent_id=chat_agent.id,
            message_id="test_msg",
            content="Test content"
        )

        assert result["status"] == "sent"
        assert result["chat_agent_id"] == chat_agent.id
        assert mock_webhook.call_count == 1

        # Verify webhook payload
        webhook_call = mock_webhook.call_args
        payload = webhook_call[0][1]  # Second argument is payload

        assert payload["chat"]["id"] == chat.id
        assert payload["chat"]["external_id"] == chat.external_id
        assert len(payload["messages"]) == 3  # All test messages


@patch('tasks.agent_tasks.Session')
@patch('tasks.agent_tasks.process_chat_message.apply_async')
def test_process_chat_message_buffer_active(mock_apply_async, mock_session_class, session, setup_data):
    """Test processing when buffer time is still active."""

    # Mock Session to return our test session
    mock_session_class.return_value.__enter__ = MagicMock(return_value=session)
    mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

    chat_agent = setup_data["chat_agent"]
    chat = setup_data["chat"]

    # Set last message time to be recent (within buffer time)
    recent_time = datetime.now(timezone.utc) - timedelta(seconds=2)
    chat.last_message_ts = recent_time
    session.add(chat)
    session.commit()

    result = process_chat_message(
        chat_agent_id=chat_agent.id,
        message_id="test_msg",
        content="Test content"
    )

    assert result["status"] == "buffered"
    assert result["chat_agent_id"] == chat_agent.id
    assert result["buffer_seconds"] == 5
    assert mock_apply_async.call_count == 1


@patch('tasks.agent_tasks.Session')
def test_process_chat_message_inactive_agent(mock_session_class, session, setup_data):
    """Test processing with inactive chat agent."""

    # Mock Session to return our test session
    mock_session_class.return_value.__enter__ = MagicMock(return_value=session)
    mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

    chat_agent = setup_data["chat_agent"]

    # Deactivate chat agent
    chat_agent.active = False
    session.add(chat_agent)
    session.commit()

    result = process_chat_message(
        chat_agent_id=chat_agent.id,
        message_id="test_msg",
        content="Test content"
    )

    assert result["status"] == "skipped"
    assert result["message"] == "ChatAgent is inactive"