import pytest
from unittest.mock import AsyncMock, patch
from sqlmodel import create_engine, Session, SQLModel
from datetime import datetime, timezone, timedelta
from apis.chats import send_message
from apis.schemas.chats import SendMessageRequest
from models.auth import User, Agent, Token, TokenUser, TokenAgent
from models.channels import Channel, Chat, Message, SenderType, PlatformType, UserChannelPermission
from models.helper import id_generator
from database import get_session
import hashlib


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


def test_send_message_as_agent_triggers_websocket(session):
    """Test that sending a message with agent token triggers WebSocket notification."""

    # Create agent
    agent = Agent(
        name="Test Agent",
        webhook_url="http://localhost:8001/webhook",
        is_fire_and_forget=False,
        buffer_time_seconds=30,
        history_msg_count=10,
        recent_msg_window_minutes=60,
        activate_for_new_conversation=True,
        is_active=True
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)

    # Create token for agent
    token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(token)
    session.commit()
    session.refresh(token)

    # Link token to agent
    token_agent = TokenAgent(token_id=token.id, agent_id=agent.id)
    session.add(token_agent)
    session.commit()

    # Create channel
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"test": "config"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)

    # Create chat
    chat = Chat(
        name="Test Chat",
        external_id="test_external",
        channel_id=channel.id,
        last_message_ts=datetime.now(timezone.utc)
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)

    # Mock WebSocket manager and message sender
    with patch('apis.chats.MessageSender') as mock_sender_class, \
         patch('apis.chats._notify_websocket_new_message') as mock_websocket:

        # Configure mocks
        mock_sender = AsyncMock()
        mock_sender_class.return_value = mock_sender
        mock_websocket.return_value = None

        # Create message request
        message_request = SendMessageRequest(
            content="Test message from agent",
            meta_data={"test": True}
        )

        # Override get_session dependency
        def override_get_session():
            return session

        # Call send_message function directly (simulating API call)
        from apis.chats import send_message
        import asyncio

        async def run_test():
            result = await send_message(
                channel_id=channel.id,
                chat_id=chat.id,
                message_data=message_request,
                token=token,
                db_session=session
            )
            return result

        result = asyncio.run(run_test())

        # Assertions
        assert result.sender_type == SenderType.AGENT
        assert result.content == "Test message from agent"

        # Verify message sender was called
        mock_sender.send_to_platform.assert_called_once()

        # Verify WebSocket notification was called for agent message
        mock_websocket.assert_called_once()

        # Check the call arguments
        call_args = mock_websocket.call_args[0]
        notification_chat = call_args[0]
        notification_message = call_args[1]
        notification_content = call_args[2]

        assert notification_chat.id == chat.id
        assert notification_message.sender_type == SenderType.AGENT
        assert notification_content == "Test message from agent"


def test_send_message_as_user_no_websocket(session):
    """Test that sending a message with user token does NOT trigger WebSocket notification."""

    # Create user
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hashlib.sha256("password".encode()).hexdigest(),
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create token for user
    token = Token(
        token_type="bearer",
        access_token=id_generator('tkn', 32)(),
        refresh_token=id_generator('ref', 32)(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        created_at=datetime.now(timezone.utc),
        is_revoked=False
    )
    session.add(token)
    session.commit()
    session.refresh(token)

    # Link token to user
    token_user = TokenUser(token_id=token.id, user_id=user.id)
    session.add(token_user)
    session.commit()

    # Create channel
    channel = Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP,
        credentials_to_send_message={"test": "config"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)

    # Create chat
    chat = Chat(
        name="Test Chat",
        external_id="test_external",
        channel_id=channel.id,
        last_message_ts=datetime.now(timezone.utc)
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)

    # Add user permission to channel
    permission = UserChannelPermission(user_id=user.id, channel_id=channel.id)
    session.add(permission)
    session.commit()

    # Mock message sender and WebSocket
    with patch('apis.chats.MessageSender') as mock_sender_class, \
         patch('apis.chats._notify_websocket_new_message') as mock_websocket:

        # Configure mocks
        mock_sender = AsyncMock()
        mock_sender_class.return_value = mock_sender
        mock_websocket.return_value = None

        # Create message request
        message_request = SendMessageRequest(
            content="Test message from user",
            meta_data={"test": True}
        )

        # Call send_message function directly
        import asyncio

        async def run_test():
            result = await send_message(
                channel_id=channel.id,
                chat_id=chat.id,
                message_data=message_request,
                token=token,
                db_session=session
            )
            return result

        result = asyncio.run(run_test())

        # Assertions
        assert result.sender_type == SenderType.USER
        assert result.content == "Test message from user"

        # Verify message sender was called
        mock_sender.send_to_platform.assert_called_once()

        # Verify WebSocket notification was NOT called for user message
        mock_websocket.assert_not_called()