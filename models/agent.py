from sqlmodel import SQLModel, Field
from .helper import id_generator


class Agent(SQLModel, table=True):
    """External service or bot that can manage conversations."""
    id: str = Field(default_factory=id_generator('agent', 10), primary_key=True)
    name: str = Field(index=True)
    api_token: str
    callback_url: str
    is_fire_and_forget: bool = Field(default=False)