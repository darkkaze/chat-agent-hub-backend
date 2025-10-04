from typing import Dict, Any, Optional
from sqlmodel import select
from datetime import datetime, timezone
from models.channels import Chat, Message, SenderType, Channel, DeliveryStatus, ChatAgent
from models.auth import Agent
from .base import WebhookHandler
from settings import logger
from tasks.agent_tasks import process_chat_message


class TelegramHandler(WebhookHandler):
    """Handler for Telegram messages via Telegram Bot API webhook."""

    async def process_inbound(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process inbound Telegram webhook."""

        logger.info("Processing Telegram webhook", extra={
            "channel_id": channel_id,
            "data_keys": list(data.keys())
        })

        # Validate payload
        if not self.validate_payload(data):
            raise ValueError("Invalid Telegram payload")

        # Extract message content
        extracted_data = self.extract_message_data(data)

        # Get or create chat
        chat = await self._get_or_create_chat(
            channel_id=channel_id,
            external_id=str(extracted_data["chat_id"]),
            contact_name=extracted_data.get("from_name", str(extracted_data["chat_id"]))
        )

        # Create message record
        message = Message(
            external_id=str(extracted_data["message_id"]),
            chat_id=chat.id,
            content=extracted_data["text"],
            sender_type=SenderType.CONTACT,
            timestamp=extracted_data["timestamp"],
            delivery_status=DeliveryStatus.SENT,
            meta_data={
                "platform": "telegram",
                "from_id": extracted_data["from_id"],
                "from_username": extracted_data.get("from_username"),
                "original_payload": data
            }
        )

        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)

        # Update chat with latest message info
        chat.last_message_ts = message.timestamp
        chat.last_sender_type = SenderType.CONTACT
        chat.last_message = message.content[:100] + "..." if len(message.content) > 100 else message.content

        self.session.add(chat)
        self.session.commit()

        # Notify websockets
        await self._notify_websocket_new_message(chat, message)

        # Trigger agent processing for all assigned agents
        await self._trigger_agent_processing(chat, message)

        logger.info("Processed Telegram message", extra={
            "message_id": message.id,
            "chat_id": chat.id,
            "external_message_id": extracted_data["message_id"]
        })

        return {
            "status": "processed",
            "message_id": message.id,
            "chat_id": chat.id,
            "content_preview": message.content[:50]
        }

    def validate_payload(self, data: Dict[str, Any]) -> bool:
        """Validate Telegram webhook payload structure."""

        # Telegram sends updates with a message object
        if "message" not in data:
            logger.warning("Telegram payload missing 'message' field")
            return False

        message = data.get("message", {})

        # Check required fields
        required_fields = ["message_id", "from", "chat", "date"]
        for field in required_fields:
            if field not in message:
                logger.warning(f"Telegram message missing required field: {field}")
                return False

        # Check for text content
        if "text" not in message:
            logger.warning("Telegram message missing 'text' field (non-text messages not supported yet)")
            return False

        return True

    def extract_message_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized message data from Telegram payload."""

        message = data.get("message", {})

        # Convert timestamp from Unix to datetime
        timestamp = datetime.fromtimestamp(
            message.get("date", 0),
            tz=timezone.utc
        )

        # Extract sender info
        from_data = message.get("from", {})
        from_name = from_data.get("first_name", "")
        if from_data.get("last_name"):
            from_name += f" {from_data.get('last_name')}"

        return {
            "message_id": message.get("message_id"),
            "from_id": from_data.get("id"),
            "from_name": from_name.strip() or str(from_data.get("id")),
            "from_username": from_data.get("username"),
            "chat_id": message.get("chat", {}).get("id"),
            "text": message.get("text", ""),
            "timestamp": timestamp
        }

    async def _get_or_create_chat(self, channel_id: str, external_id: str,
                                contact_name: str) -> Chat:
        """Get existing chat or create new one."""

        # Try to find existing chat
        chat_statement = select(Chat).where(
            Chat.channel_id == channel_id,
            Chat.external_id == external_id
        )
        chat = self.session.exec(chat_statement).first()

        if chat:
            return chat

        # Create new chat
        chat = Chat(
            name=contact_name,
            external_id=external_id,
            channel_id=channel_id,
            meta_data={
                "contact_name": contact_name,
                "platform": "telegram"
            }
        )

        self.session.add(chat)
        self.session.commit()
        self.session.refresh(chat)

        # Auto-assign agents that are configured for new conversations
        await self._auto_assign_agents(chat)

        logger.info("Created new Telegram chat", extra={
            "chat_id": chat.id,
            "external_id": external_id,
            "channel_id": channel_id
        })

        return chat

    async def _auto_assign_agents(self, chat: Chat):
        """Auto-assign agents that are configured for new conversations."""

        # Find agents configured for auto-assignment
        agent_statement = select(Agent).where(
            Agent.activate_for_new_conversation == True,
            Agent.is_active == True
        )
        agents = self.session.exec(agent_statement).all()

        for agent in agents:
            chat_agent = ChatAgent(
                chat_id=chat.id,
                agent_id=agent.id,
                active=True
            )
            self.session.add(chat_agent)

        if agents:
            self.session.commit()
            logger.info("Auto-assigned agents to new chat", extra={
                "chat_id": chat.id,
                "agent_count": len(agents)
            })

    async def _trigger_agent_processing(self, chat: Chat, message: Message):
        """Trigger agent processing for all assigned ChatAgents."""

        # Get all active ChatAgents for this chat
        chat_agents_statement = select(ChatAgent).where(
            ChatAgent.chat_id == chat.id,
            ChatAgent.active == True
        )
        chat_agents = self.session.exec(chat_agents_statement).all()

        if not chat_agents:
            logger.info("No active agents for chat", extra={"chat_id": chat.id})
            return

        # Send Celery task for each ChatAgent
        tasks_sent = []
        for chat_agent in chat_agents:
            try:
                task = process_chat_message.delay(
                    chat_agent_id=chat_agent.id,
                    message_id=message.id,
                    content=message.content
                )
                tasks_sent.append({
                    "chat_agent_id": chat_agent.id,
                    "agent_id": chat_agent.agent_id,
                    "task_id": task.id
                })

            except Exception as e:
                logger.error("Celery task failed", extra={
                    "chat_agent_id": chat_agent.id,
                    "agent_id": chat_agent.agent_id,
                    "error": str(e)
                })

        if tasks_sent:
            logger.info("Tasks sent to agents", extra={
                "chat_id": chat.id,
                "count": len(tasks_sent),
                "tasks": tasks_sent
            })

    async def _notify_websocket_new_message(self, chat: Chat, message: Message):
        """Send WebSocket notification for new message."""

        try:
            import json
            from ws_service.manager import manager

            notification_data = {
                "type": "new_message",
                "chat_id": chat.id,
                "channel_id": chat.channel_id,
                "message_id": message.id,
                "sender_type": message.sender_type.value,
                "timestamp": message.timestamp.isoformat(),
                "message_type": "text",
                "content": message.content,
                "preview": message.content[:100],
                "external_id": message.external_id or "",
                "chat_name": chat.name,
                "chat_external_id": chat.external_id or ""
            }

            await manager.broadcast(json.dumps(notification_data))

        except Exception as e:
            logger.error("Failed to send WebSocket notification", extra={
                "error": str(e),
                "chat_id": chat.id,
                "message_id": message.id
            }, exc_info=True)
