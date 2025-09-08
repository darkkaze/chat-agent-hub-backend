from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from database import get_session
from models.auth import User, Token, UserRole
from .schemas.auth import CreateUserRequest, UpdateUserRequest, UserResponse, MessageResponse
from helpers.auth import get_auth_token, require_admin, require_admin_or_self
import hashlib

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> UserResponse:
    """Get user information"""
    
    # Get the user
    user_statement = select(User).where(User.id == user_id)
    user = db_session.exec(user_statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Return user data without sensitive information
    return UserResponse.model_validate(user)


@router.get("/")
async def list_users(
    is_active: bool = True,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> list[UserResponse]:
    """List all users."""
    # Get users filtered by is_active status
    user_statement = select(User).where(User.is_active == is_active)
    users = db_session.exec(user_statement).all()
    
    # Return users without sensitive information
    return [UserResponse.model_validate(user) for user in users]


@router.post("/")
async def create_user(
    user_data: CreateUserRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> UserResponse:
    """Create new user (Admins only)."""
    
    # Validate admin access
    await require_admin(token=token)
    
    # Hash the password
    hashed_password = hashlib.sha256(user_data.password.encode()).hexdigest()
    
    # Create user with validated data
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        phone=user_data.phone, 
        hashed_password=hashed_password,
        role=UserRole[user_data.role] if user_data.role else UserRole.MEMBER,
        is_active=user_data.is_active
    )
    
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    
    # Return user data without sensitive information
    return UserResponse.model_validate(new_user)


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    user_data: UpdateUserRequest,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> UserResponse:
    """Update user information 
    Admins or token.user_id == user_id"""
    
    # Validate admin access or self-update
    await require_admin_or_self(token=token, user_id=user_id)
    
    # Get the user to update
    user_statement = select(User).where(User.id == user_id)
    user = db_session.exec(user_statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields that are provided (only non-None values)
    if user_data.username is not None:
        user.username = user_data.username
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.phone is not None:
        user.phone = user_data.phone
    if user_data.role is not None:
        user.role = UserRole[user_data.role]
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    # Hash password if provided
    if user_data.password is not None:
        hashed_password = hashlib.sha256(user_data.password.encode()).hexdigest()
        user.hashed_password = hashed_password
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Return user data without sensitive information
    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    hard: bool = False,
    token: Token = Depends(get_auth_token),
    db_session: Session = Depends(get_session)
) -> MessageResponse:
    """Delete a user (Admins only). 
    Soft delete (default) sets is_active=False, hard delete removes from database
    """
    
    # Validate admin access
    await require_admin(token=token)
    
    # Get the user to delete
    user_statement = select(User).where(User.id == user_id)
    user = db_session.exec(user_statement).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if hard:
        # Hard delete - remove from database
        db_session.delete(user)
        db_session.commit()
        return MessageResponse(message="User deleted successfully")
    else:
        # Soft delete - mark as inactive
        user.is_active = False
        db_session.add(user)
        db_session.commit()
        return MessageResponse(message="User soft-deleted successfully")