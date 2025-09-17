from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
from settings import logger


class ConnectionManager:
    """WebSocket connection manager for real-time notifications."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connection established", extra={
            "total_connections": len(self.active_connections)
        })

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket connection closed", extra={
                "total_connections": len(self.active_connections)
            })

    async def broadcast(self, message: str):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            logger.debug("No active WebSocket connections to broadcast to")
            return

        logger.info("Broadcasting message to WebSocket clients", extra={
            "message_preview": message[:100] + "..." if len(message) > 100 else message,
            "connection_count": len(self.active_connections)
        })

        # Create a copy to avoid modification during iteration
        connections_copy = self.active_connections.copy()
        disconnected_connections = []

        for connection in connections_copy:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning("Failed to send message to WebSocket client", extra={
                    "error": str(e)
                })
                disconnected_connections.append(connection)

        # Remove failed connections
        for connection in disconnected_connections:
            self.disconnect(connection)

    async def send_to_connection(self, websocket: WebSocket, message: str):
        """Send message to a specific connection."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning("Failed to send message to specific WebSocket client", extra={
                "error": str(e)
            })
            self.disconnect(websocket)

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)


# Global manager instance
manager = ConnectionManager()