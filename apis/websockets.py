from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ws_service.manager import manager
from settings import logger
import json

router = APIRouter(tags=["websockets"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = None
):
    """
    WebSocket endpoint for real-time notifications.

    Query parameter:
    - token: Bearer token for authentication (optional for development)
    """

    # For development, we might allow connections without auth
    # In production, you should validate the token here
    if token:
        try:
            # TODO: Validate token if needed
            # auth_token = await get_auth_token_from_query(token)
            pass
        except Exception as e:
            logger.warning("WebSocket authentication failed", extra={
                "error": str(e),
                "token": token[:20] + "..." if token and len(token) > 20 else token
            })
            await websocket.close(code=1008, reason="Authentication failed")
            return

    await manager.connect(websocket)

    try:
        # Send welcome message
        welcome_message = {
            "type": "connection_established",
            "message": "WebSocket connection established successfully",
            "active_connections": manager.get_connection_count()
        }
        await manager.send_to_connection(websocket, json.dumps(welcome_message))

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (could be pings, auth updates, etc.)
                data = await websocket.receive_text()

                # Parse incoming message
                try:
                    message = json.loads(data)
                    message_type = message.get("type")

                    if message_type == "ping":
                        # Respond to ping with pong
                        pong_response = {
                            "type": "pong",
                            "timestamp": message.get("timestamp"),
                            "server_time": "2025-01-01T00:00:00Z"  # You could use actual time
                        }
                        await manager.send_to_connection(websocket, json.dumps(pong_response))

                    elif message_type == "subscribe":
                        # Handle subscription to specific channels/chats
                        # For now, just acknowledge
                        ack_response = {
                            "type": "subscription_ack",
                            "subscribed_to": message.get("channels", [])
                        }
                        await manager.send_to_connection(websocket, json.dumps(ack_response))

                    else:
                        logger.debug("Unknown WebSocket message type", extra={
                            "message_type": message_type,
                            "message": message
                        })

                except json.JSONDecodeError:
                    logger.warning("Invalid JSON received from WebSocket client", extra={
                        "data": data[:100] + "..." if len(data) > 100 else data
                    })

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error("Error handling WebSocket message", extra={
                    "error": str(e)
                })
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket connection error", extra={
            "error": str(e)
        })
    finally:
        manager.disconnect(websocket)


@router.get("/ws/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    return {
        "active_connections": manager.get_connection_count(),
        "status": "running"
    }