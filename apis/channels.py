from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models.channels import Channel, UserChannelPermission, PlatformType
from models.auth import Token
from helpers.auth import get_auth_token, require_user_or_agent, can_access_all_channels, require_admin_or_agent
from .schemas.channels import ChannelResponse, CreateChannelRequest, UpdateChannelRequest
from apis.schemas.auth import MessageResponse
from typing import List

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("/platforms")
async def get_platform_types() -> List[str]:
    """Get available platform types (no authentication required)."""
    return [platform.value for platform in PlatformType]


@router.get("")
async def list_channels(
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> List[ChannelResponse]:
    """List channels user has access to."""
    
    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)
    
    # Check if token holder can access all channels
    if can_access_all_channels(token):
        # Admin users and agents can see all channels
        statement = select(Channel)
        channels = db_session.exec(statement).all()
    else:
        # Member users can only see channels they have permission to access
        if not token.user:
            # This shouldn't happen if require_user_or_agent passed, but just in case
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User access required"
            )
            
        # Query channels where user has explicit permission
        statement = (
            select(Channel)
            .join(UserChannelPermission)
            .where(UserChannelPermission.user_id == token.user.id)
        )
        channels = db_session.exec(statement).all()
    
    # Return channels without sensitive credential information
    return [ChannelResponse.model_validate(channel) for channel in channels]


@router.post("")
async def create_channel(
    channel_data: CreateChannelRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChannelResponse:
    """Connect a new channel.
    (admin and agent only)
    """
    
    # Validate admin or agent access
    await require_admin_or_agent(token=token, db_session=db_session)
    
    # Create new channel
    new_channel = Channel(
        name=channel_data.name,
        platform=channel_data.platform,
        credentials_to_send_message=channel_data.credentials_to_send_message,
        api_to_send_message=channel_data.api_to_send_message
    )
    
    db_session.add(new_channel)
    db_session.commit()
    db_session.refresh(new_channel)
    
    # Return channel data without sensitive credentials
    return ChannelResponse.model_validate(new_channel)


@router.get("/{channel_id}")
async def get_channel(
    channel_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChannelResponse:
    """Get channel details."""
    
    # Validate that token is associated with a user or agent
    await require_user_or_agent(token=token, db_session=db_session)
    
    # Get the channel
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Check if token holder can access this channel
    if can_access_all_channels(token):
        # Admin users and agents can see any channel
        pass
    else:
        # Member users can only see channels they have permission to access
        if not token.user:
            # This shouldn't happen if require_user_or_agent passed, but just in case
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User access required"
            )
            
        # Check if user has explicit permission to this channel
        permission_statement = select(UserChannelPermission).where(
            UserChannelPermission.user_id == token.user.id,
            UserChannelPermission.channel_id == channel_id
        )
        permission = db_session.exec(permission_statement).first()
        
        if not permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to access this channel"
            )
    
    # Return channel data without sensitive credential information
    return ChannelResponse.model_validate(channel)


@router.put("/{channel_id}")
async def update_channel(
    channel_id: str,
    channel_data: UpdateChannelRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> ChannelResponse:
    """Update channel information (admin and agent only)."""
    
    # Validate admin or agent access
    await require_admin_or_agent(token=token, db_session=db_session)
    
    # Get the channel to update
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Update fields that are provided (only non-None values)
    if channel_data.name is not None:
        channel.name = channel_data.name
    if channel_data.credentials_to_send_message is not None:
        channel.credentials_to_send_message = channel_data.credentials_to_send_message
    if channel_data.api_to_send_message is not None:
        channel.api_to_send_message = channel_data.api_to_send_message
    # Note: buffer_time_seconds, history_msg_count, recent_msg_window_minutes moved to Agent model
    
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    
    # Return channel data without sensitive credentials
    return ChannelResponse.model_validate(channel)


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MessageResponse:
    """Disconnect a channel."""
    
    # Validate admin or agent access
    await require_admin_or_agent(token=token, db_session=db_session)
    
    # Get the channel to delete
    channel_statement = select(Channel).where(Channel.id == channel_id)
    channel = db_session.exec(channel_statement).first()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )
    
    # Delete associated records first (to avoid foreign key constraints)
    
    # Delete UserChannelPermission records
    permission_statement = select(UserChannelPermission).where(UserChannelPermission.channel_id == channel_id)
    permissions = db_session.exec(permission_statement).all()
    for permission in permissions:
        db_session.delete(permission)
    
    # Note: ChannelAgent records removed per model changes
    
    # Delete the channel itself
    db_session.delete(channel)
    db_session.commit()
    
    # Return success confirmation
    return MessageResponse(message="Channel deleted successfully")