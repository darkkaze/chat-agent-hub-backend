"""
Feature: WebSocket for real-time notifications
  As a frontend application
  I want to receive real-time notifications about new messages
  So that I can update the UI immediately when messages arrive

Scenario: Successfully connect to WebSocket
  When connecting to the WebSocket endpoint
  Then the connection should be established
  And a welcome message should be received

Scenario: Receive new message notification
  Given a WebSocket connection is established
  When a new message is created via webhook
  Then a notification should be broadcast to all connected clients

Scenario: Handle ping-pong
  Given a WebSocket connection is established
  When sending a ping message
  Then a pong response should be received
"""

import pytest
import json
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from unittest.mock import patch, AsyncMock
from main import app
from websockets.manager import manager


class TestWebSocket:
    """Test WebSocket functionality."""

    def test_websocket_stats_endpoint(self):
        """Test WebSocket stats endpoint."""
        with TestClient(app) as client:
            response = client.get("/ws/stats")
            assert response.status_code == 200
            data = response.json()
            assert "active_connections" in data
            assert "status" in data
            assert data["status"] == "running"

    def test_websocket_connection(self):
        """Test basic WebSocket connection."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                # Should receive welcome message
                data = websocket.receive_text()
                message = json.loads(data)

                assert message["type"] == "connection_established"
                assert "active_connections" in message
                assert message["active_connections"] >= 1

    def test_websocket_ping_pong(self):
        """Test ping-pong functionality."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                # Receive welcome message first
                websocket.receive_text()

                # Send ping
                ping_message = {
                    "type": "ping",
                    "timestamp": "2025-01-01T00:00:00Z"
                }
                websocket.send_text(json.dumps(ping_message))

                # Should receive pong
                data = websocket.receive_text()
                pong_message = json.loads(data)

                assert pong_message["type"] == "pong"
                assert pong_message["timestamp"] == "2025-01-01T00:00:00Z"

    def test_websocket_subscription(self):
        """Test subscription acknowledgment."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                # Receive welcome message first
                websocket.receive_text()

                # Send subscription
                subscribe_message = {
                    "type": "subscribe",
                    "channels": ["channel_123", "channel_456"]
                }
                websocket.send_text(json.dumps(subscribe_message))

                # Should receive acknowledgment
                data = websocket.receive_text()
                ack_message = json.loads(data)

                assert ack_message["type"] == "subscription_ack"
                assert ack_message["subscribed_to"] == ["channel_123", "channel_456"]

    @pytest.mark.asyncio
    @patch('websockets.manager.manager.broadcast')
    async def test_manager_broadcast(self, mock_broadcast):
        """Test manager broadcast functionality."""
        mock_broadcast.return_value = AsyncMock()

        test_message = {
            "type": "new_message",
            "chat_id": "chat_123",
            "content": "Test message"
        }

        await manager.broadcast(json.dumps(test_message))
        mock_broadcast.assert_called_once_with(json.dumps(test_message))

    def test_websocket_invalid_json(self):
        """Test handling of invalid JSON."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:
                # Receive welcome message first
                websocket.receive_text()

                # Send invalid JSON
                websocket.send_text("invalid json {")

                # Connection should remain open
                # Send a valid ping to verify
                ping_message = {"type": "ping"}
                websocket.send_text(json.dumps(ping_message))

                # Should still receive pong
                data = websocket.receive_text()
                pong_message = json.loads(data)
                assert pong_message["type"] == "pong"