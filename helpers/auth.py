from fastapi import Depends, HTTPException, status, Header
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from models.auth import Token, Agent, TokenUser, TokenAgent, User
from database import get_session
from datetime import datetime, timezone


async def get_auth_token(
    authorization: str = Header(),
    db_session: Session = Depends(get_session)
) -> Token:
    """Extract and validate token from Authorization header, returning Token object with relationships loaded."""
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    token_string = authorization.split(" ")[1]
    
    # Single query with joins to load Token with User and Agent relationships
    statement = (
        select(Token)
        .options(
            joinedload(Token.token_users).joinedload(TokenUser.user),
            joinedload(Token.token_agents).joinedload(TokenAgent.agent)
        )
        .where(
            Token.access_token == token_string,
            Token.is_revoked == False,
            Token.expires_at > datetime.now(timezone.utc)
        )
    )
    
    token = db_session.exec(statement).first()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return token


def get_user_from_token(token: Token, db_session: Session = None) -> User | None:
    """Get user associated with a token (using preloaded relationship)."""
    return token.user


async def require_admin(
    token: Token,
    db_session: Session = None
) -> None:
    """Validate that the authenticated user is an admin. Raises 403 if not admin."""
    
    # Get user from token (using preloaded relationship)
    from models.auth import UserRole
    user = token.user
    
    if user and user.role == UserRole.ADMIN:
        return  # User is admin, allow access
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required"
    )


async def require_admin_or_self(
    token: Token,
    user_id: str,
    db_session: Session = None
) -> None:
    """Validate that the authenticated user is admin or owns the user_id. Raises 403 if neither."""
    
    # Get user from token (using preloaded relationship)
    from models.auth import UserRole
    user = token.user
    
    if not user:
        # Token might be associated with an agent, not a user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User access required"
        )
    
    # Check if user is admin OR if they're updating their own profile
    if user.role == UserRole.ADMIN or user.id == user_id:
        return  # Allow access
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required or can only update own profile"
    )


async def require_user_or_agent(
    token: Token,
    db_session: Session = None
) -> None:
    """Validate that the token is associated with either a user or an agent. Raises 403 if neither."""
    
    # Token must be associated with either a user or agent
    if not token.user and not token.agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Valid user or agent authentication required"
        )
    
    # If it's a user, they must be active
    if token.user and not token.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # If it's an agent, they must be active  
    if token.agent and not token.agent.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent is inactive"
        )


def can_access_all_channels(token: Token) -> bool:
    """Check if token holder (user or agent) can access all channels.
    
    Returns:
        True if ADMIN user or any AGENT, False if MEMBER user
    """
    from models.auth import UserRole
    
    # Agents can access all channels
    if token.agent:
        return True
    
    # Admin users can access all channels    
    if token.user and token.user.role == UserRole.ADMIN:
        return True
        
    # Member users need explicit permissions
    return False


async def require_admin_or_agent(
    token: Token,
    db_session: Session = None
) -> None:
    """Validate that the token is associated with an admin user or any agent. Raises 403 if neither."""
    from models.auth import UserRole
    
    # Check if it's an agent (agents can perform admin-like operations)
    if token.agent:
        if not token.agent.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent is inactive"
            )
        return  # Active agent can proceed
    
    # Check if it's an admin user
    if token.user:
        if not token.user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        if token.user.role == UserRole.ADMIN:
            return  # Admin user can proceed
    
    # Neither admin user nor agent
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin or agent access required"
    )


def check_channel_access(token: Token, channel, db_session: Session):
    """Helper function to check if token holder can access the channel."""
    if can_access_all_channels(token):
        # Admin users and agents can access any channel
        return
    
    # Member users need explicit permission
    # Get user from token_users relationship
    from models.auth import TokenUser
    from models.channels import UserChannelPermission
    token_user_statement = select(TokenUser).where(TokenUser.token_id == token.id)
    token_user = db_session.exec(token_user_statement).first()
    
    if not token_user:
        raise HTTPException(
            status_code=403,
            detail="User access required for this channel"
        )
    
    # Check if user has explicit permission to this channel
    permission_statement = select(UserChannelPermission).where(
        UserChannelPermission.user_id == token_user.user_id,
        UserChannelPermission.channel_id == channel.id
    )
    permission = db_session.exec(permission_statement).first()
    
    if not permission:
        raise HTTPException(
            status_code=403,
            detail="No permission to access this channel"
        )