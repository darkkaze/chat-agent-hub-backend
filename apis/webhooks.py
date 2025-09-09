from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select
from database import get_session
from models.channels import Channel, PlatformType
from webhooks.base import WebhookHandlerFactory
from settings import logger
from typing import Dict, Any

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/inbound/{platform}/{channel_id}")
async def receive_inbound_webhook(
    platform: str,
    channel_id: str,
    request: Request,
    db_session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Receive messages and events from WhatsApp, Telegram, etc."""
    
    logger.info("Webhook received", extra={
        "platform": platform,
        "channel_id": channel_id
    })
    
    try:
        # Get request body as dict
        webhook_data = {}
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            webhook_data = await request.json()
        elif "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            webhook_data = dict(form_data)
        else:
            # Try to get as form data (Twilio default)
            try:
                form_data = await request.form()
                webhook_data = dict(form_data)
            except:
                webhook_data = await request.json()
        
        # Validate channel exists
        channel_statement = select(Channel).where(Channel.id == channel_id)
        channel = db_session.exec(channel_statement).first()
        
        if not channel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Channel {channel_id} not found"
            )
        
        # Convert platform string to enum (uppercase)
        try:
            platform_enum = PlatformType(platform.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported platform: {platform}"
            )
        
        # Validate platform matches channel
        if channel.platform != platform_enum:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Platform mismatch. Channel is {channel.platform}, received {platform_enum}"
            )
        
        # Get appropriate handler
        try:
            handler = WebhookHandlerFactory.get_handler(platform_enum, db_session)
        except (NotImplementedError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=str(e)
            )
        
        # Process the webhook
        result = await handler.process_inbound(webhook_data, channel_id)
        
        logger.info("Webhook processed successfully", extra={
            "platform": platform,
            "channel_id": channel_id,
            "result": result
        })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing webhook", extra={
            "platform": platform,
            "channel_id": channel_id,
            "error": str(e)
        }, exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )


@router.post("/agent/{chat_id}")
async def receive_agent_response(chat_id: str):
    """Receive responses from external agents in async mode."""
    pass