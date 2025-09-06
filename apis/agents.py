from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("")
async def create_agent():
    """Register a new external agent."""
    pass


@router.get("")
async def list_agents():
    """List configured agents."""
    pass


@router.post("/channels/{channel_id}/agents/{agent_id}")
async def associate_agent_to_channel(channel_id: str, agent_id: str):
    """Associate an agent to a channel."""
    pass