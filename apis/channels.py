from fastapi import APIRouter

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
async def list_channels():
    """List channels user has access to."""
    pass


@router.post("")
async def create_channel():
    """Connect a new channel."""
    pass


@router.get("/{channel_id}")
async def get_channel(channel_id: str):
    """Get channel details."""
    pass


@router.delete("/{channel_id}")
async def delete_channel(channel_id: str):
    """Disconnect a channel."""
    pass