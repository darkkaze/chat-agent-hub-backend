from typing import Dict, Any, Optional
from sqlmodel import select
from datetime import datetime, timezone
from models.channels import Chat, Message, SenderType, Channel, DeliveryStatus, ChatAgent
from models.auth import Agent
from .base import WebhookHandler
from settings import logger
from tasks.agent_tasks import process_chat_message


class WhapiHandler(WebhookHandler):
    """Handler for WhatsApp messages via WHAPI webhook."""

    async def process_inbound(self, data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process inbound WhatsApp webhook from WHAPI."""

        logger.info("Processing WHAPI webhook", extra={
            "channel_id": channel_id,
            "data_keys": list(data.keys())
        })

        # Validate payload
        if not self.validate_payload(data):
            raise ValueError("Invalid WHAPI payload")

        # Process messages
        results = []
        messages = data.get("messages", [])

        for message_data in messages:
            result = await self.process_message(message_data, channel_id)
            results.append(result)

        return {
            "status": "success",
            "processed_messages": len(results),
            "results": results
        }

    async def process_message(self, message_data: Dict[str, Any], channel_id: str) -> Dict[str, Any]:
        """Process individual WHAPI message."""

        # Extract message content
        extracted_data = self.extract_message_data_from_single(message_data)

        # Skip messages sent by us
        if message_data.get("from_me", False):
            logger.info("Skipping outbound message", extra={
                "message_id": message_data.get("id"),
                "channel_id": channel_id
            })
            return {"status": "skipped", "reason": "outbound_message"}

        # Get or create chat
        chat = await self._get_or_create_chat(
            channel_id=channel_id,
            external_id=extracted_data["from_number"],
            contact_phone=extracted_data["from_number"],
            contact_name=extracted_data.get("from_name", extracted_data["from_number"])
        )

        # Handle different message types
        message_content = ""
        message_type = extracted_data.get("message_type", "text")

        if message_type == "text":
            message_content = extracted_data["text_body"]
        else:
            # For non-text messages, create a placeholder
            message_content = f"[{message_type.upper()} MESSAGE]"
            logger.info("Received non-text message", extra={
                "message_type": message_type,
                "chat_id": chat.id
            })

        # Create message record
        message = Message(
            external_id=extracted_data["message_id"],
            chat_id=chat.id,
            content=message_content,
            sender_type=SenderType.CONTACT,
            timestamp=extracted_data["timestamp"],
            meta_data={
                "platform": "whapi",
                "message_type": message_type,
                "source": message_data.get("source", "unknown"),
                "original_payload": message_data
            }
        )

        self.session.add(message)
        self.session.commit()
        self.session.refresh(message)

        # Update chat with latest message info
        chat.last_message_ts = message.timestamp
        chat.last_sender_type = SenderType.CONTACT
        chat.last_message = message_content[:100] + "..." if len(message_content) > 100 else message_content

        self.session.add(chat)
        self.session.commit()

        # Notify websockets
        await self._notify_websocket_new_message(chat, message)

        # Trigger agent processing for all assigned agents
        await self._trigger_agent_processing(chat, message)

        logger.info("Processed WHAPI message", extra={
            "message_id": message.id,
            "chat_id": chat.id,
            "external_message_id": extracted_data["message_id"]
        })

        return {
            "status": "processed",
            "message_id": message.id,
            "chat_id": chat.id,
            "content_preview": message_content[:50]
        }

    def validate_payload(self, data: Dict[str, Any]) -> bool:
        """Validate WHAPI webhook payload structure."""

        # Check for required top-level fields
        if "messages" not in data:
            logger.warning("WHAPI payload missing 'messages' field")
            return False

        messages = data.get("messages", [])
        if not isinstance(messages, list) or len(messages) == 0:
            logger.warning("WHAPI payload has empty or invalid messages array")
            return False

        # Validate each message
        for message in messages:
            if not self._validate_single_message(message):
                return False

        return True

    def _validate_single_message(self, message: Dict[str, Any]) -> bool:
        """Validate individual message structure."""

        required_fields = ["id", "type", "chat_id", "timestamp", "from"]

        for field in required_fields:
            if field not in message:
                logger.warning(f"WHAPI message missing required field: {field}")
                return False

        # Validate message type specific fields
        message_type = message.get("type")
        if message_type == "text":
            if "text" not in message or "body" not in message.get("text", {}):
                logger.warning("WHAPI text message missing text.body field")
                return False

        return True

    def extract_message_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized message data from WHAPI payload."""

        # For WHAPI, we process the first message in the array
        messages = data.get("messages", [])
        if not messages:
            raise ValueError("No messages found in WHAPI payload")

        return self.extract_message_data_from_single(messages[0])

    def extract_message_data_from_single(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data from a single WHAPI message."""

        # Convert timestamp from Unix to datetime
        timestamp = datetime.fromtimestamp(
            message.get("timestamp", 0),
            tz=timezone.utc
        )

        # Extract text content
        text_body = ""
        if message.get("type") == "text" and "text" in message:
            text_body = message["text"].get("body", "")

        return {
            "message_id": message.get("id"),
            "from_number": message.get("from"),
            "from_name": message.get("from_name", ""),
            "chat_id": message.get("chat_id"),
            "text_body": text_body,
            "message_type": message.get("type", "text"),
            "timestamp": timestamp,
            "source": message.get("source", "unknown")
        }

    async def _get_or_create_chat(self, channel_id: str, external_id: str,
                                contact_phone: str, contact_name: str) -> Chat:
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
            name=contact_name or contact_phone,
            external_id=external_id,
            channel_id=channel_id,
            meta_data={
                "contact_phone": contact_phone,
                "contact_name": contact_name,
                "platform": "whapi"
            }
        )

        self.session.add(chat)
        self.session.commit()
        self.session.refresh(chat)

        # Auto-assign agents that are configured for new conversations
        await self._auto_assign_agents(chat)

        logger.info("Created new WHAPI chat", extra={
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