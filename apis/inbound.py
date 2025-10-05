from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select
from database import get_session
from models.channels import Channel, PlatformType
from inbound.base import InboundHandlerFactory
from settings import logger
from typing import Dict, Any

router = APIRouter(prefix="/inbound", tags=["inbound"])


@router.post("/{platform}/{channel_id}")
async def receive_inbound_message(
    platform: str,
    channel_id: str,
    request: Request,
    db_session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Receive inbound messages and events from WhatsApp, Telegram, etc."""

    logger.info("Inbound message received", extra={
        "platform": platform,
        "channel_id": channel_id
    })
    
    try:
        # Get request body as dict
        inbound_data = {}
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            inbound_data = await request.json()
        elif "application/x-www-form-urlencoded" in content_type:
            form_data = await request.form()
            inbound_data = dict(form_data)
        else:
            # Try to get as form data (Twilio default)
            try:
                form_data = await request.form()
                inbound_data = dict(form_data)
            except:
                inbound_data = await request.json()
        
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
            handler = InboundHandlerFactory.get_handler(platform_enum, db_session)
        except (NotImplementedError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=str(e)
            )

        # Process the inbound message
        result = await handler.process_inbound(inbound_data, channel_id)

        logger.info("Inbound message processed successfully", extra={
            "platform": platform,
            "channel_id": channel_id,
            "result": result
        })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing inbound message", extra={
            "platform": platform,
            "channel_id": channel_id,
            "error": str(e)
        }, exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing inbound message"
        )


@router.post("/agent/{chat_id}")
async def receive_agent_response(chat_id: str):
    """Receive responses from external agents in async mode."""
    pass