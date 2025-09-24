from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models.menu import Menu
from models.auth import Token
from helpers.auth import get_auth_token, require_admin
from .schemas.menu import CreateMenuRequest, UpdateMenuRequest, MenuResponse, MenuListResponse
from apis.schemas.auth import MessageResponse
from typing import List

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("/")
async def list_menu_items(
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MenuListResponse:
    """List all menu items (authenticated users only)."""

    # Any authenticated user can see menu items
    # No specific role requirement

    # Get all menu items
    statement = select(Menu)
    menus = db_session.exec(statement).all()

    return MenuListResponse(
        menus=[MenuResponse.model_validate(menu) for menu in menus],
        total_count=len(menus)
    )


@router.post("/")
async def create_menu_item(
    menu_data: CreateMenuRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MenuResponse:
    """Create new menu item (Admins only)."""

    # Validate admin access
    await require_admin(token=token)

    # Create menu item
    new_menu = Menu(
        icon=menu_data.icon,
        url=menu_data.url
    )

    db_session.add(new_menu)
    db_session.commit()
    db_session.refresh(new_menu)

    return MenuResponse.model_validate(new_menu)


@router.get("/{menu_id}")
async def get_menu_item(
    menu_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MenuResponse:
    """Get specific menu item (authenticated users only)."""

    # Any authenticated user can see menu items

    # Get the menu item
    menu_statement = select(Menu).where(Menu.id == menu_id)
    menu = db_session.exec(menu_statement).first()

    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    return MenuResponse.model_validate(menu)


@router.put("/{menu_id}")
async def update_menu_item(
    menu_id: str,
    menu_data: UpdateMenuRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MenuResponse:
    """Update menu item (Admins only)."""

    # Validate admin access
    await require_admin(token=token)

    # Get the menu item to update
    menu_statement = select(Menu).where(Menu.id == menu_id)
    menu = db_session.exec(menu_statement).first()

    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Update fields that are provided (only non-None values)
    if menu_data.icon is not None:
        menu.icon = menu_data.icon
    if menu_data.url is not None:
        menu.url = menu_data.url

    db_session.add(menu)
    db_session.commit()
    db_session.refresh(menu)

    return MenuResponse.model_validate(menu)


@router.delete("/{menu_id}")
async def delete_menu_item(
    menu_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MessageResponse:
    """Delete menu item (Admins only)."""

    # Validate admin access
    await require_admin(token=token)

    # Get the menu item to delete
    menu_statement = select(Menu).where(Menu.id == menu_id)
    menu = db_session.exec(menu_statement).first()

    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Delete the menu item
    db_session.delete(menu)
    db_session.commit()

    return MessageResponse(message="Menu item deleted successfully")