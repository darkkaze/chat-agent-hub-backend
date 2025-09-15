#!/usr/bin/env python3
"""
Management commands for Agent Hub.

Usage:
    python manage.py init_db
    python manage.py check_db
    python manage.py reset_db
    python manage.py create_admin <username> <password>
"""

import sys
import hashlib
from sqlmodel import SQLModel, text
from database import engine, get_session
from settings import logger
from models.auth import User, UserRole, Agent, Token, TokenUser, TokenAgent
# Import all models to ensure tables are created
from models.channels import Channel, UserChannelPermission, Chat, Message
from models.boards import Board, Task
from models.documents import Document, ChatDocument, TaskDocument
from models.notes import Note, ChatNote, TaskNote


def init_db():
    """Initialize database tables."""
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")


def check_db():
    """Check database connection and tables."""
    try:
        with next(get_session()) as session:
            result = session.exec(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = result.fetchall()
            logger.info(f"Database connected. Found {len(tables)} tables: {[t[0] for t in tables]}")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)


def reset_db():
    """Drop and recreate all database tables."""
    logger.warning("Dropping all database tables...")
    SQLModel.metadata.drop_all(engine)
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database reset successfully")


def create_admin(username: str, password: str):
    """Create an admin user."""
    try:
        with next(get_session()) as session:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            admin_user = User(
                username=username,
                hashed_password=hashed_password,
                role=UserRole.ADMIN,
                is_active=True
            )
            
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            
            logger.info(f"Admin user '{username}' created successfully with ID: {admin_user.id}")
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command> [args]")
        print("Commands:")
        print("  init_db                        - Initialize database tables")
        print("  check_db                       - Check database connection")
        print("  reset_db                       - Drop and recreate all tables")
        print("  create_admin <username> <pass> - Create admin user")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "init_db":
        init_db()
    elif command == "check_db":
        check_db()
    elif command == "reset_db":
        reset_db()
    elif command == "create_admin":
        if len(sys.argv) != 4:
            print("Usage: python manage.py create_admin <username> <password>")
            sys.exit(1)
        username = sys.argv[2]
        password = sys.argv[3]
        create_admin(username, password)
    else:
        print(f"Unknown command: {command}")
        print("Run 'python manage.py' to see available commands")
        sys.exit(1)


if __name__ == "__main__":
    main()