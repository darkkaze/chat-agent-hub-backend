from fastapi import APIRouter

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("")
async def list_chats():
    """Get chat list with filters by channel, status or assigned user."""
    pass


@router.get("/{chat_id}")
async def get_chat(chat_id: str):
    """Get specific conversation details."""
    pass


@router.post("/{chat_id}/assign")
async def assign_chat(chat_id: str):
    """Assign chat to a team user."""
    pass


@router.get("/{chat_id}/messages")
async def get_chat_messages(chat_id: str):
    """Get latest N messages from chat with pagination."""
    pass


@router.post("/{chat_id}/messages")
async def send_message(chat_id: str):
    """Send message to chat."""
    pass