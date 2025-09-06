from sqlmodel import Session, create_engine
from typing import Generator
import redis
from settings import DATABASE_URL, REDIS_URL

engine = create_engine(DATABASE_URL, echo=True)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def get_session() -> Generator[Session, None, None]:
    """Database session dependency for FastAPI dependency injection."""
    with Session(engine) as session:
        yield session


def get_redis() -> redis.Redis:
    """Redis client dependency for FastAPI dependency injection."""
    return redis_client