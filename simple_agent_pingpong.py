#!/usr/bin/env python3
"""
Simple Agent Ping-Pong Server
Receives webhook from agent_tasks._send_to_agent_webhook and responds with "pong"
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import requests
import sqlite3

app = FastAPI(title="Simple Agent Ping-Pong", version="1.0.0")


class Message(BaseModel):
    """Message structure from webhook payload."""
    id: str
    external_id: Optional[str] = None
    chat_id: str
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class Chat(BaseModel):
    """Chat structure from webhook payload."""
    id: str
    external_id: Optional[str] = None
    channel_id: str


class WebhookPayload(BaseModel):
    """Expected payload structure from _send_to_agent_webhook."""
    chat: Chat
    messages: List[Message]


def get_access_token():
    """Get first available access token from SQLite database."""
    conn = sqlite3.connect('agent_hub.db')
    cursor = conn.cursor()
    cursor.execute("SELECT access_token FROM token WHERE is_revoked = 0 ORDER BY created_at DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


async def send_pong_message(chat_id: str, channel_id: str):
    """Send 'pong' message using the API."""
    print('sending message')
    try:
        # Get token
        access_token = get_access_token()
        if not access_token:
            print("ERROR: Could not get access token")
            return False

        # API endpoint
        url = f"http://localhost:8000/channels/{channel_id}/chats/{chat_id}/messages"

        # Headers with authentication
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # Message payload
        message_data = {
            "content": "pong",
            "meta_data": {
                "agent_response": True,
                "agent_name": "simple_pingpong_agent"
            }
        }

        # Send the message
        response = requests.post(url, headers=headers, json=message_data)

        if response.status_code == 200:
            print(f"✅ Pong message sent successfully to chat {chat_id}")
            return True
        else:
            print(f"❌ Failed to send pong message. Status: {response.status_code}, Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error sending pong message: {str(e)}")
        return False


@app.post("/webhook")
async def agent_webhook(payload: WebhookPayload):
    """
    Receive webhook from agent_tasks._send_to_agent_webhook.
    Print the payload and respond with 'pong' via API.
    """

    # Print the received payload
    print("=" * 50)
    print("WEBHOOK RECEIVED:")
    print(f"Chat ID: {payload.chat.id}")
    print(f"Channel ID: {payload.chat.channel_id}")
    print(f"External ID: {payload.chat.external_id}")
    print(f"Messages count: {len(payload.messages)}")
    print()

    # Print each message
    for i, message in enumerate(payload.messages, 1):
        print(f"Message {i}:")
        print(f"  ID: {message.id}")
        print(f"  Content: {message.content}")
        print(f"  Timestamp: {message.timestamp}")
        print(f"  Metadata: {message.metadata}")
        print()

    print("Full JSON payload:")
    print(json.dumps(payload.dict(), indent=2))
    print("=" * 50)

    # Send pong message via API
    success = await send_pong_message(payload.chat.id, payload.chat.channel_id)

    # Respond with status
    return {
        "response": "pong",
        "status": "received",
        "message_sent": success
    }


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Simple Agent Ping-Pong Server is running", "status": "ok"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    print("Starting Simple Agent Ping-Pong Server on port 8001...")
    print("Webhook endpoint: http://localhost:8001/webhook")
    uvicorn.run(app, host="0.0.0.0", port=8001)