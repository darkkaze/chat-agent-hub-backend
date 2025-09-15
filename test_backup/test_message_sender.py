"""
Unit tests for MessageSender service.
Tests the outbound message sending logic with mocked handlers.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from sqlmodel import create_engine, Session, SQLModel
from models.channels import Channel, Chat, Message, PlatformType, SenderType
from outbound.message_sender import MessageSender
from datetime import datetime


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def sample_channel():
    return Channel(
        name="Test Channel",
        platform=PlatformType.WHATSAPP_TWILIO,
        credentials_to_send_message={"user": "AC123", "token": "secret"}
    )


@pytest.fixture
def sample_chat():
    return Chat(
        name="Test Chat",
        external_id="+1234567890",
    )


@pytest.fixture
def sample_message():
    return Message(
        chat_id="chat_123",
        content="Hello World!",
        sender_type=SenderType.USER,
        meta_data={}  # Ensure empty metadata dict
    )


@pytest.mark.asyncio
async def test_send_to_platform_success(session, sample_channel, sample_chat, sample_message):
    """Test successful message sending with platform response."""
    
    # Given a MessageSender and mocked successful platform response
    sender = MessageSender(session)
    
    mock_handler = AsyncMock()
    mock_handler.send_message.return_value = {
        "status": "success",
        "external_id": "MSG123456",
        "platform_status": "queued",
        "to": "+1234567890",
        "from": "+0987654321"
    }
    
    with patch('outbound.message_sender.OutboundHandlerFactory.get_handler', return_value=mock_handler):
        # When sending message to platform
        await sender.send_to_platform(sample_chat, sample_message, sample_channel)
        
        # Then the handler should be called with correct parameters
        mock_handler.send_message.assert_called_once_with(sample_chat, sample_message, sample_channel)
        
        # And message metadata should be updated with success info
        assert sample_message.external_id == "MSG123456"
        assert sample_message.meta_data["platform_sent"] is True
        assert sample_message.meta_data["platform_status"] == "queued"
        assert sample_message.meta_data["platform_external_id"] == "MSG123456"
        assert sample_message.meta_data["sent_to"] == "+1234567890"
        assert sample_message.meta_data["sent_from"] == "+0987654321"


@pytest.mark.asyncio
async def test_send_to_platform_api_error(session, sample_channel, sample_chat, sample_message):
    """Test message sending with API error response."""
    
    # Given a MessageSender and mocked API error response
    sender = MessageSender(session)
    
    mock_handler = AsyncMock()
    mock_handler.send_message.return_value = {
        "status": "error",
        "error": "Invalid phone number",
        "error_code": "21211",
        "error_type": "validation"
    }
    
    with patch('outbound.message_sender.OutboundHandlerFactory.get_handler', return_value=mock_handler):
        # When sending message to platform
        await sender.send_to_platform(sample_chat, sample_message, sample_channel)
        
        # Then the handler should be called
        mock_handler.send_message.assert_called_once()
        
        # And message metadata should be updated with error info
        assert sample_message.external_id is None  # Should not be updated on error
        assert sample_message.meta_data["platform_sent"] is False
        assert sample_message.meta_data["platform_error"] == "Invalid phone number"
        assert sample_message.meta_data["platform_error_code"] == "21211"
        assert sample_message.meta_data["platform_error_type"] == "validation"


@pytest.mark.asyncio
async def test_send_to_platform_handler_not_implemented(session, sample_channel, sample_chat, sample_message):
    """Test message sending when platform handler is not implemented."""
    
    # Given a MessageSender and mocked NotImplementedError
    sender = MessageSender(session)
    
    with patch('outbound.message_sender.OutboundHandlerFactory.get_handler', 
               side_effect=NotImplementedError("Handler for TELEGRAM not implemented yet")):
        # When sending message to platform
        await sender.send_to_platform(sample_chat, sample_message, sample_channel)
        
        # Then message metadata should indicate not supported
        assert sample_message.meta_data["platform_sent"] is False
        assert "not implemented yet" in sample_message.meta_data["platform_error"]
        assert sample_message.meta_data["platform_error_type"] == "not_supported"


@pytest.mark.asyncio
async def test_send_to_platform_invalid_configuration(session, sample_channel, sample_chat, sample_message):
    """Test message sending with invalid channel configuration."""
    
    # Given a MessageSender and mocked ValueError for invalid config
    sender = MessageSender(session)
    
    with patch('outbound.message_sender.OutboundHandlerFactory.get_handler', 
               side_effect=ValueError("Invalid Twilio channel configuration")):
        # When sending message to platform
        await sender.send_to_platform(sample_chat, sample_message, sample_channel)
        
        # Then message metadata should indicate configuration error
        assert sample_message.meta_data["platform_sent"] is False
        assert "Invalid Twilio channel configuration" in sample_message.meta_data["platform_error"]
        assert sample_message.meta_data["platform_error_type"] == "not_supported"


@pytest.mark.asyncio
async def test_send_to_platform_unexpected_exception(session, sample_channel, sample_chat, sample_message):
    """Test message sending with unexpected exception."""
    
    # Given a MessageSender and mocked unexpected exception
    sender = MessageSender(session)
    
    mock_handler = AsyncMock()
    mock_handler.send_message.side_effect = Exception("Network timeout")
    
    with patch('outbound.message_sender.OutboundHandlerFactory.get_handler', return_value=mock_handler):
        # When sending message to platform
        await sender.send_to_platform(sample_chat, sample_message, sample_channel)
        
        # Then message metadata should indicate unexpected error
        assert sample_message.meta_data["platform_sent"] is False
        assert sample_message.meta_data["platform_error"] == "Unexpected error during send"
        assert sample_message.meta_data["platform_error_type"] == "unexpected"


@pytest.mark.asyncio
async def test_send_to_platform_partial_success_response(session, sample_channel, sample_chat, sample_message):
    """Test message sending with partial success response (missing some fields)."""
    
    # Given a MessageSender and mocked partial success response
    sender = MessageSender(session)
    
    mock_handler = AsyncMock()
    mock_handler.send_message.return_value = {
        "status": "success",
        "external_id": "MSG789",
        # Missing platform_status, to, from fields
    }
    
    with patch('outbound.message_sender.OutboundHandlerFactory.get_handler', return_value=mock_handler):
        # When sending message to platform
        await sender.send_to_platform(sample_chat, sample_message, sample_channel)
        
        # Then message should still be updated correctly with available data
        assert sample_message.external_id == "MSG789"
        assert sample_message.meta_data["platform_sent"] is True
        assert sample_message.meta_data["platform_external_id"] == "MSG789"
        assert sample_message.meta_data.get("platform_status") is None
        assert sample_message.meta_data.get("sent_to") is None
        assert sample_message.meta_data.get("sent_from") is None


@pytest.mark.asyncio
async def test_send_to_platform_database_persistence(session, sample_channel, sample_chat, sample_message):
    """Test that message updates are persisted to database."""
    
    # Given a MessageSender with mocked success response
    sender = MessageSender(session)
    
    mock_handler = AsyncMock()
    mock_handler.send_message.return_value = {
        "status": "success",
        "external_id": "MSG999"
    }
    
    with patch('outbound.message_sender.OutboundHandlerFactory.get_handler', return_value=mock_handler):
        # When sending message to platform
        await sender.send_to_platform(sample_chat, sample_message, sample_channel)
        
        # Then message should be updated with external_id and metadata
        assert sample_message.external_id == "MSG999"
        assert sample_message.meta_data["platform_sent"] is True
        assert sample_message.meta_data["platform_external_id"] == "MSG999"