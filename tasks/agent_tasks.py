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