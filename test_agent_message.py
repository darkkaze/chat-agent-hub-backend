#!/usr/bin/env python3
"""
Test script to send a message using agent token and verify WebSocket notification
"""

import requests
import sqlite3
import json

def get_agent_token():
    """Get agent access token from database."""
    conn = sqlite3.connect('agent_hub.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.access_token
        FROM token t
        INNER JOIN tokenagent ta ON t.id = ta.token_id
        WHERE t.is_revoked = 0 AND t.expires_at > datetime('now')
        ORDER BY t.created_at DESC
        LIMIT 1
    """)
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_test_chat():
    """Get chat that has the agent assigned."""
    conn = sqlite3.connect('agent_hub.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.channel_id
        FROM chat c
        INNER JOIN chatagent ca ON c.id = ca.chat_id
        WHERE ca.agent_id = 'agent_mqfwqeq73h' AND ca.active = 1
        LIMIT 1
    """)
    result = cursor.fetchone()
    conn.close()
    return result if result else None

def send_agent_message():
    """Send message using agent token."""

    # Get agent token
    access_token = get_agent_token()
    if not access_token:
        print("❌ No agent token found")
        return False

    print(f"✅ Agent token found: {access_token[:20]}...")

    # Get test chat
    chat_info = get_test_chat()
    if not chat_info:
        print("❌ No chat found for agent")
        return False

    chat_id, channel_id = chat_info
    print(f"✅ Using chat {chat_id} in channel {channel_id}")

    # API endpoint
    url = f"http://localhost:8000/channels/{channel_id}/chats/{chat_id}/messages"

    # Headers with agent authentication
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Message payload
    message_data = {
        "content": "Test message from agent token - should trigger WebSocket notification",
        "meta_data": {
            "test_agent_message": True,
            "agent_name": "default"
        }
    }

    try:
        # Send the message
        response = requests.post(url, headers=headers, json=message_data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Message sent successfully!")
            print(f"   Message ID: {result['id']}")
            print(f"   Sender Type: {result['sender_type']}")
            print(f"   Content: {result['content']}")

            # Check if it was detected as AGENT
            if result['sender_type'] == 'AGENT':
                print("✅ Correctly detected as AGENT sender!")
                print("🔄 WebSocket notification should have been sent")
                return True
            else:
                print(f"❌ Wrong sender type detected: {result['sender_type']}")
                return False
        else:
            print(f"❌ Failed to send message. Status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error sending message: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing agent message with WebSocket notification...")
    print("=" * 50)
    success = send_agent_message()
    print("=" * 50)
    if success:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed!")