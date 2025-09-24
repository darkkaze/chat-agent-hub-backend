from sqlmodel import SQLModel, Field
from models.helper import id_generator


class Menu(SQLModel, table=True):
    """Menu items for navigation."""
    id: str = Field(default_factory=id_generator('menu', 10), primary_key=True)
    name: str = Field(description="Display name for menu item", index=True)
    icon: str = Field(description="MDI string name")
    url: str = Field(description="URL path for navigation", index=True)