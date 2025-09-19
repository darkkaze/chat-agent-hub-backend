from sqlmodel import Session, select
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
import requests
import time
from settings import logger
from models.channels import ChatAgent, Chat, Message
from models.auth import Agent
from database import engine

# Import configured Celery app from worker
from worker import celery_app


def _get_recent_messages(chat_id: str, history_msg_count: int, recent_msg_window_minutes: int) -> List[Message]:
    """Get recent messages for a chat based on agent configuration."""

    with Session(engine) as session:
        # Calculate cutoff time
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=recent_msg_window_minutes)

        # Query messages within time window and limit by count
        statement = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .where(Message.timestamp >= cutoff_time)
            .order_by(Message.timestamp.desc())
            .limit(history_msg_count)
        )

        messages = session.exec(statement).all()

        # Return in chronological order (oldest first)
        return list(reversed(messages))


def _send_to_agent_webhook(webhook_url: str, payload: Dict[str, Any], max_retries: int = 3) -> bool:
    """Send payload to agent webhook with retry logic."""

    for attempt in range(max_retries):
        try:
            logger.info("Sending to agent webhook", extra={
                "webhook_url": webhook_url,
                "attempt": attempt + 1,
                "max_retries": max_retries
            })

            response = requests.post(
                webhook_url,
                json=payload,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )

            # Check if response is successful (2xx status codes)
            if response.status_code >= 200 and response.status_code < 300:
                logger.info("Webhook call successful", extra={
                    "webhook_url": webhook_url,
                    "status_code": response.status_code,
                    "attempt": attempt + 1
                })
                return True
            else:
                logger.warning("Webhook returned non-success status", extra={
                    "webhook_url": webhook_url,
                    "status_code": response.status_code,
                    "attempt": attempt + 1,
                    "response_text": response.text[:500]  # First 500 chars
                })

        except requests.exceptions.RequestException as e:
            logger.error("Webhook request failed", extra={
                "webhook_url": webhook_url,
                "attempt": attempt + 1,
                "error": str(e)
            })

        # Sleep before retry (except on last attempt)
        if attempt < max_retries - 1:
            logger.info("Sleeping before retry", extra={
                "webhook_url": webhook_url,
                "sleep_seconds": 5,
                "next_attempt": attempt + 2
            })
            time.sleep(5)

    logger.error("All webhook attempts failed", extra={
        "webhook_url": webhook_url,
        "total_attempts": max_retries
    })
    return False


@celery_app.task
def agent_callback(chat_id: str, agent_id: str, message_data: dict):
    """Process agent callback response (dummy implementation)."""
    # TODO: Implement actual agent callback processing
    logger.debug("Agent callback received", extra={
        "chat_id": chat_id,
        "agent_id": agent_id
    })
    return {"status": "processed", "chat_id": chat_id, "agent_id": agent_id}


@celery_app.task
def process_chat_message(chat_agent_id: str, message_id: str, content: str):
    """Process new chat message for specific agent with buffer algorithm."""

    logger.info("Starting process_chat_message", extra={
        "chat_agent_id": chat_agent_id,
        "message_id": message_id
    })

    with Session(engine) as session:
        # 1. Load ChatAgent and related Agent, Chat info
        chat_agent_statement = select(ChatAgent).where(ChatAgent.id == chat_agent_id)
        chat_agent = session.exec(chat_agent_statement).first()

        if not chat_agent:
            logger.error("ChatAgent not found", extra={"chat_agent_id": chat_agent_id})
            return {"status": "error", "message": "ChatAgent not found"}

        # Check if ChatAgent is active
        if not chat_agent.active:
            logger.info("ChatAgent is inactive, skipping", extra={"chat_agent_id": chat_agent_id})
            return {"status": "skipped", "message": "ChatAgent is inactive"}

        # Load Agent
        agent_statement = select(Agent).where(Agent.id == chat_agent.agent_id)
        agent = session.exec(agent_statement).first()

        if not agent or not agent.is_active:
            logger.error("Agent not found or inactive", extra={
                "agent_id": chat_agent.agent_id,
                "chat_agent_id": chat_agent_id
            })
            return {"status": "error", "message": "Agent not found or inactive"}

        if not agent.webhook_url:
            logger.error("Agent has no webhook_url", extra={
                "agent_id": agent.id,
                "chat_agent_id": chat_agent_id
            })
            return {"status": "error", "message": "Agent has no webhook_url"}

        # Load Chat
        chat_statement = select(Chat).where(Chat.id == chat_agent.chat_id)
        chat = session.exec(chat_statement).first()

        if not chat:
            logger.error("Chat not found", extra={
                "chat_id": chat_agent.chat_id,
                "chat_agent_id": chat_agent_id
            })
            return {"status": "error", "message": "Chat not found"}

        # 2. Implement buffer algorithm
        now = datetime.now(timezone.utc)
        buffer_cutoff = now - timedelta(seconds=agent.buffer_time_seconds)

        logger.info("Checking buffer algorithm", extra={
            "chat_id": chat.id,
            "last_message_ts": chat.last_message_ts.isoformat() if chat.last_message_ts else None,
            "buffer_cutoff": buffer_cutoff.isoformat(),
            "buffer_time_seconds": agent.buffer_time_seconds
        })

        # If last message is older than buffer time, send immediately
        # Handle timezone-aware vs naive datetime comparison
        last_message_ts = chat.last_message_ts
        if last_message_ts and last_message_ts.tzinfo is None:
            last_message_ts = last_message_ts.replace(tzinfo=timezone.utc)

        if last_message_ts and last_message_ts < buffer_cutoff:
            logger.info("Buffer time elapsed, sending immediately", extra={
                "chat_id": chat.id,
                "chat_agent_id": chat_agent_id
            })

            # 3. Get recent messages
            messages = _get_recent_messages(
                chat_id=chat.id,
                history_msg_count=agent.history_msg_count,
                recent_msg_window_minutes=agent.recent_msg_window_minutes
            )

            # 4. Prepare payload
            payload = {
                "chat": {
                    "id": chat.id,
                    "external_id": chat.external_id,
                    "channel_id": chat.channel_id
                },
                "messages": [
                    {
                        "id": msg.id,
                        "external_id": msg.external_id,
                        "chat_id": msg.chat_id,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.meta_data
                    }
                    for msg in messages
                ]
            }

            logger.info("Sending payload to agent", extra={
                "chat_agent_id": chat_agent_id,
                "agent_id": agent.id,
                "webhook_url": agent.webhook_url,
                "message_count": len(messages)
            })

            # 5. Send to webhook with retries
            success = _send_to_agent_webhook(agent.webhook_url, payload)

            if success:
                return {
                    "status": "sent",
                    "chat_agent_id": chat_agent_id,
                    "agent_id": agent.id,
                    "message_count": len(messages)
                }
            else:
                return {
                    "status": "failed",
                    "chat_agent_id": chat_agent_id,
                    "agent_id": agent.id,
                    "message": "Webhook delivery failed after retries"
                }

        else:
            # Schedule task for later execution
            delay_seconds = agent.buffer_time_seconds
            eta = now + timedelta(seconds=delay_seconds)

            logger.info("Scheduling buffered execution", extra={
                "chat_id": chat.id,
                "chat_agent_id": chat_agent_id,
                "delay_seconds": delay_seconds,
                "eta": eta.isoformat()
            })

            # Schedule the same task for later
            process_chat_message.apply_async(
                args=[chat_agent_id, message_id, content],
                eta=eta
            )

            return {
                "status": "buffered",
                "chat_agent_id": chat_agent_id,
                "scheduled_eta": eta.isoformat(),
                "buffer_seconds": delay_seconds
            }