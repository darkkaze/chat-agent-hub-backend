from sqlmodel import SQLModel, Field
from models.helper import id_generator


class Menu(SQLModel, table=True):
    """Menu items for navigation."""
    id: str = Field(default_factory=id_generator('menu', 10), primary_key=True)
    icon_svg: str = Field(description="SVG icon as string")
    url: str = Field(description="URL path for navigation", index=True)