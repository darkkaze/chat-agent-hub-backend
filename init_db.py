#!/usr/bin/env python3
"""
Database initialization script for Agent Hub.

Usage:
    python init_db.py
"""

from sqlmodel import SQLModel
from database import engine
from settings import logger


def init_database():
    """Create all database tables."""
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully")


if __name__ == "__main__":
    init_database()