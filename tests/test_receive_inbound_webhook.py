import pytest
from sqlmodel import create_engine, Session, SQLModel
from fastapi import Request
from datetime import datetime, timezone
from models.channels import Channel, Chat, Message, PlatformType, SenderType, DeliveryStatus
from models.auth import User, UserRole, Agent, Token
from database import get_session
from apis.webhooks import receive_inbound_webhook


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


class MockRequest:
    """Mock Request object for testing."""
    
    def __init__(self, json_data=None, form_data=None, content_type="application/x-www-form-urlencoded"):
        self._json_data = json_data or {}
        self._form_data = form_data or {}
        self.headers = {"content-type": content_type}
    
    async def json(self):
        return self._json_data
    
    async def form(self):
        return self._form_data


@pytest.mark.asyncio
async def test_receive_whatsapp_text_message_success(session):
    """Test successful WhatsApp text message processing."""
    
    # Given a WhatsApp channel
    channel = Channel(
        name="WhatsApp Test",
        platform=PlatformType.WHATSAPP_TWILIO,
        credentials_to_send_message={"token": "test_token"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    # And valid Twilio webhook data
    webhook_data = {
        "MessageSid": "SM1234567890abcdef1234567890abcdef",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+0987654321",
        "Body": "Hello, this is a test message!"
    }
    
    # When receiving the webhook
    mock_request = MockRequest(form_data=webhook_data)
    
    result = await receive_inbound_webhook(
        platform="whatsapp_twilio",
        channel_id=channel.id,
        request=mock_request,
        db_session=session
    )
    
    # Then it should process successfully
    assert result["status"] == "success"
    assert result["message_type"] == "text"
    assert "chat_id" in result
    assert "message_id" in result
    
    # And create a chat
    created_chat = session.get(Chat, result["chat_id"])
    assert created_chat is not None
    assert created_chat.external_id == "+1234567890"
    assert created_chat.channel_id == channel.id
    assert created_chat.last_message_ts is not None
    
    # And create a message
    created_message = session.get(Message, result["message_id"])
    assert created_message is not None
    assert created_message.content == "Hello, this is a test message!"
    assert created_message.sender_type == SenderType.CONTACT
    assert created_message.delivery_status == DeliveryStatus.SENT
    assert created_message.chat_id == created_chat.id
    assert created_message.meta_data["from_number"] == "+1234567890"
    assert created_message.meta_data["twilio_sid"] == "SM1234567890abcdef1234567890abcdef"


@pytest.mark.asyncio
async def test_receive_whatsapp_voice_message_success(session):
    """Test successful WhatsApp voice message processing."""
    
    # Given a WhatsApp channel
    channel = Channel(
        name="WhatsApp Test",
        platform=PlatformType.WHATSAPP_TWILIO,
        credentials_to_send_message={"token": "test_token"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    # And valid voice message webhook data
    webhook_data = {
        "MessageSid": "SM1234567890abcdef1234567890abcdef",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+0987654321",
        "MediaUrl0": "https://api.twilio.com/voice.ogg",
        "MediaContentType0": "audio/ogg"
    }
    
    # When receiving the webhook
    mock_request = MockRequest(form_data=webhook_data)
    
    result = await receive_inbound_webhook(
        platform="whatsapp_twilio",
        channel_id=channel.id,
        request=mock_request,
        db_session=session
    )
    
    # Then it should process successfully
    assert result["status"] == "success"
    assert result["message_type"] == "voice"
    
    # And create a message with voice content
    created_message = session.get(Message, result["message_id"])
    assert created_message is not None
    assert "[Voice Message]" in created_message.content
    assert "https://api.twilio.com/voice.ogg" in created_message.content
    assert created_message.sender_type == SenderType.CONTACT
    assert created_message.delivery_status == DeliveryStatus.SENT
    assert created_message.meta_data["message_type"] == "voice"
    assert created_message.meta_data["media_url"] == "https://api.twilio.com/voice.ogg"


@pytest.mark.asyncio
async def test_receive_webhook_existing_chat(session):
    """Test that webhook reuses existing chat."""
    
    # Given a WhatsApp channel
    channel = Channel(
        name="WhatsApp Test",
        platform=PlatformType.WHATSAPP_TWILIO,
        credentials_to_send_message={"token": "test_token"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    # And an existing chat
    existing_chat = Chat(
        name="Test Chat",
        external_id="+1234567890",
        channel_id=channel.id,
        last_message_ts=datetime.now(timezone.utc),
        meta_data={"contact_phone": "+1234567890"}
    )
    session.add(existing_chat)
    session.commit()
    session.refresh(existing_chat)
    
    # And webhook data from the same contact
    webhook_data = {
        "MessageSid": "SM1234567890abcdef1234567890abcdef",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+0987654321",
        "Body": "Second message from same contact"
    }
    
    # When receiving the webhook
    mock_request = MockRequest(form_data=webhook_data)
    
    result = await receive_inbound_webhook(
        platform="whatsapp_twilio",
        channel_id=channel.id,
        request=mock_request,
        db_session=session
    )
    
    # Then it should reuse the existing chat
    assert result["chat_id"] == existing_chat.id
    
    # And update the last_message_ts
    session.refresh(existing_chat)
    # Handle timezone comparison - database might store naive datetime
    last_message_ts = existing_chat.last_message_ts
    if last_message_ts.tzinfo is None:
        last_message_ts = last_message_ts.replace(tzinfo=timezone.utc)
    assert last_message_ts > datetime.now(timezone.utc).replace(microsecond=0)


@pytest.mark.asyncio
async def test_receive_webhook_channel_not_found(session):
    """Test webhook with non-existent channel."""
    
    webhook_data = {
        "MessageSid": "SM1234567890abcdef1234567890abcdef",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+0987654321",
        "Body": "Test message"
    }
    
    mock_request = MockRequest(form_data=webhook_data)
    
    with pytest.raises(Exception) as exc_info:
        await receive_inbound_webhook(
            platform="whatsapp_twilio",
            channel_id="nonexistent_channel",
            request=mock_request,
            db_session=session
        )
    
    assert "Channel nonexistent_channel not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_receive_webhook_platform_mismatch(session):
    """Test webhook with platform mismatch."""
    
    # Given a Telegram channel
    channel = Channel(
        name="Telegram Test",
        platform=PlatformType.TELEGRAM,
        credentials_to_send_message={"token": "test_token"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    webhook_data = {
        "MessageSid": "SM1234567890abcdef1234567890abcdef",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+0987654321",
        "Body": "Test message"
    }
    
    mock_request = MockRequest(form_data=webhook_data)
    
    # When sending WhatsApp webhook to Telegram channel
    with pytest.raises(Exception) as exc_info:
        await receive_inbound_webhook(
            platform="whatsapp_twilio",
            channel_id=channel.id,
            request=mock_request,
            db_session=session
        )
    
    # Then it should fail with platform mismatch
    assert "Platform mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_receive_webhook_unsupported_platform(session):
    """Test webhook with unsupported platform."""
    
    # Given a WhatsApp channel
    channel = Channel(
        name="WhatsApp Test",
        platform=PlatformType.WHATSAPP_TWILIO,
        credentials_to_send_message={"token": "test_token"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    webhook_data = {"message": "test"}
    mock_request = MockRequest(form_data=webhook_data)
    
    # When using unsupported platform
    with pytest.raises(Exception) as exc_info:
        await receive_inbound_webhook(
            platform="unsupported_platform",
            channel_id=channel.id,
            request=mock_request,
            db_session=session
        )
    
    # Then it should fail
    assert "Unsupported platform" in str(exc_info.value)


@pytest.mark.asyncio
async def test_receive_webhook_json_content_type(session):
    """Test webhook with JSON content type."""
    
    # Given a WhatsApp channel
    channel = Channel(
        name="WhatsApp Test",
        platform=PlatformType.WHATSAPP_TWILIO,
        credentials_to_send_message={"token": "test_token"}
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    
    # And JSON webhook data
    webhook_data = {
        "MessageSid": "SM1234567890abcdef1234567890abcdef",
        "From": "whatsapp:+1234567890",
        "To": "whatsapp:+0987654321",
        "Body": "JSON message"
    }
    
    # When receiving JSON webhook
    mock_request = MockRequest(
        json_data=webhook_data, 
        content_type="application/json"
    )
    
    result = await receive_inbound_webhook(
        platform="whatsapp_twilio",
        channel_id=channel.id,
        request=mock_request,
        db_session=session
    )
    
    # Then it should process successfully
    assert result["status"] == "success"
    
    # And create the message
    created_message = session.get(Message, result["message_id"])
    assert created_message.content == "JSON message"
    assert created_message.delivery_status == DeliveryStatus.SENT