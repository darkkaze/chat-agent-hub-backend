from celery import Celery

# This will be properly configured later
celery_app = Celery('agent_hub')


@celery_app.task
def agent_callback(chat_id: str, agent_id: str, message_data: dict):
    """Process agent callback response (dummy implementation)."""
    # TODO: Implement actual agent callback processing
    print(f"Processing agent callback for chat {chat_id} from agent {agent_id}")
    print(f"Message data: {message_data}")
    return {"status": "processed", "chat_id": chat_id, "agent_id": agent_id}


@celery_app.task
def process_chat_message(chat_agent_id: str, message_id: str, content: str):
    """Process new chat message for specific agent."""
    # TODO: Implement actual message processing logic
    # This should:
    # 1. Load ChatAgent and related Agent info
    # 2. Prepare message context for agent
    # 3. Send message to agent webhook_url
    # 4. Handle agent response if needed

    print(f"Processing message {message_id} for ChatAgent {chat_agent_id}")
    print(f"Message content: {content}")

    return {
        "status": "processed",
        "chat_agent_id": chat_agent_id,
        "message_id": message_id,
        "content_length": len(content)
    }