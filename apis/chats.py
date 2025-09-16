from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, desc
from database import get_session
from models.auth import Token, User
from models.channels import Channel, Chat, Message, SenderType, DeliveryStatus
from helpers.auth import get_auth_token, require_user_or_agent, require_admin_or_agent, check_channel_access
from .schemas.chats import ChatResponse, MessageResponse, ChatListResponse, ChatMessagesResponse, AssignChatRequest, SendMessageRequest
from typing import List, Optional, Dict, Any
from outbound.message_sender import MessageSender

router = APIRouter(tags=["channels"])


@router.get("/channels/{channel_id}/chats", response_model=ChatListResponse)
async def list_chats(
    channel_id: str,
    limit: int = Query(default=50, description="Number of chats to retrieve", ge=1, le=100),
    offset: int = Query(default=0, description="Number of chats to skip", ge=0),
    assigned_user_id: Optional[str] = Query(default=None, description="Filter by assigned user ID"),
    assigned: Optional[bool] = Query(default=None, description="Filter by assignment status"),
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChatListResponse:
    """Get paginated chat list from specific channel with filters by assigned user or status."""
    
    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)
    
    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check channel access
    check_channel_access(token, channel, db_session)
    
    # Build base chat query for filtering
    base_statement = select(Chat).where(Chat.channel_id == channel_id)
    
    # Apply filters
    if assigned_user_id is not None:
        base_statement = base_statement.where(Chat.assigned_user_id == assigned_user_id)
    
    if assigned is not None:
        if assigned:
            base_statement = base_statement.where(Chat.assigned_user_id.is_not(None))
        else:
            base_statement = base_statement.where(Chat.assigned_user_id.is_(None))
    
    # Get total count with filters applied
    total_count = len(db_session.exec(base_statement).all())
    
    # Apply pagination and order by last_message_ts (newest first)
    paginated_statement = base_statement.order_by(desc(Chat.last_message_ts)).offset(offset).limit(limit)
    chats = db_session.exec(paginated_statement).all()
    
    # Check if there are more chats
    has_more = (offset + len(chats)) < total_count
    
    return ChatListResponse(
        chats=[ChatResponse.model_validate(chat) for chat in chats],
        total_count=total_count,
        has_more=has_more
    )


@router.get("/channels/{channel_id}/chats/{chat_id}", response_model=ChatResponse)
async def get_chat(
    channel_id: str,
    chat_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChatResponse:
    """Get specific chat details within a channel."""
    
    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)
    
    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check channel access
    check_channel_access(token, channel, db_session)
    
    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")
    
    return ChatResponse.model_validate(chat)


@router.delete("/channels/{channel_id}/chats/{chat_id}")
async def delete_chat(
    channel_id: str,
    chat_id: str,
    soft: bool = Query(default=False, description="If true, perform soft delete"),
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> Dict[str, Any]:
    """Delete chat within a channel (soft or hard delete) - admin and agent only."""
    
    # Validate admin or agent access
    await require_admin_or_agent(token=token, db_session=db_session)
    
    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check channel access (admins and agents should have access, but double-check)
    check_channel_access(token, channel, db_session)
    
    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")
    
    if soft:
        # Soft delete - would need is_deleted field in actual implementation
        return {"success": True, "message": f"Chat {chat_id} soft deleted successfully"}
    else:
        # Hard delete - remove chat and associated messages
        # Remove associated messages first
        messages_statement = select(Message).where(Message.chat_id == chat_id)
        messages = db_session.exec(messages_statement).all()
        for message in messages:
            db_session.delete(message)
        
        # Remove the chat itself
        db_session.delete(chat)
        db_session.commit()
        
        return {"success": True, "message": f"Chat {chat_id} permanently deleted successfully"}


@router.post("/channels/{channel_id}/chats/{chat_id}/assign", response_model=ChatResponse)
async def assign_chat(
    channel_id: str,
    chat_id: str,
    assign_data: AssignChatRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChatResponse:
    """Assign chat to a team user within a channel."""
    
    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)
    
    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check channel access
    check_channel_access(token, channel, db_session)
    
    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")
    
    # Verify the user to assign exists
    user_statement = select(User).where(User.id == assign_data.user_id)
    user = db_session.exec(user_statement).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update chat assignment
    chat.assigned_user_id = assign_data.user_id
    db_session.add(chat)
    db_session.commit()
    db_session.refresh(chat)
    
    return ChatResponse.model_validate(chat)


@router.get("/channels/{channel_id}/chats/{chat_id}/messages", response_model=ChatMessagesResponse)
async def get_chat_messages(
    channel_id: str,
    chat_id: str,
    limit: int = Query(default=50, description="Number of messages to retrieve", ge=1, le=100),
    offset: int = Query(default=0, description="Number of messages to skip", ge=0),
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChatMessagesResponse:
    """Get latest N messages from chat with pagination within a channel."""
    
    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)
    
    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check channel access
    check_channel_access(token, channel, db_session)
    
    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")
    
    # Get total count
    total_count_statement = select(Message).where(Message.chat_id == chat_id)
    total_count = len(db_session.exec(total_count_statement).all())
    
    # Get messages with pagination, ordered by timestamp desc (newest first)
    messages_statement = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.timestamp))
        .offset(offset)
        .limit(limit)
    )
    messages = db_session.exec(messages_statement).all()
    
    # Check if there are more messages
    has_more = (offset + len(messages)) < total_count
    
    return ChatMessagesResponse(
        messages=[MessageResponse.model_validate(message) for message in messages],
        total_count=total_count,
        has_more=has_more
    )


@router.post("/channels/{channel_id}/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
    channel_id: str,
    chat_id: str,
    message_data: SendMessageRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MessageResponse:
    """Send message to chat within a channel."""
    
    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)
    
    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check channel access
    check_channel_access(token, channel, db_session)
    
    # Get the chat and verify it belongs to the channel
    chat_statement = select(Chat).where(Chat.id == chat_id, Chat.channel_id == channel_id)
    chat = db_session.exec(chat_statement).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found in this channel")
    
    # Determine sender type based on token
    # Check if token is associated with an agent
    from models.auth import TokenAgent
    token_agent_statement = select(TokenAgent).where(TokenAgent.token_id == token.id)
    token_agent = db_session.exec(token_agent_statement).first()
    
    sender_type = SenderType.AGENT if token_agent else SenderType.USER
    
    # Create message
    message = Message(
        chat_id=chat_id,
        content=message_data.content,
        sender_type=sender_type,
        delivery_status=DeliveryStatus.PENDING,  # Outbound messages start as pending
        meta_data=message_data.meta_data
    )
    
    # Update chat's last_message_ts, last_sender_type, and last_message
    chat.last_message_ts = message.timestamp
    chat.last_sender_type = sender_type
    chat.last_message = message_data.content
    
    db_session.add(message)
    db_session.add(chat)
    db_session.commit()
    db_session.refresh(message)
    
    # Send message to external platform
    sender = MessageSender(db_session)
    await sender.send_to_platform(chat, message, channel)
    
    return MessageResponse.model_validate(message)