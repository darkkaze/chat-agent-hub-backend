from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/inbound/{platform}/{channel_id}")
async def receive_inbound_webhook(platform: str, channel_id: str):
    """Receive messages and events from WhatsApp, Telegram, etc."""
    pass


@router.post("/agent/{chat_id}")
async def receive_agent_response(chat_id: str):
    """Receive responses from external agents in async mode."""
    pass