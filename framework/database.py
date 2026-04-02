from typing import AsyncGenerator, Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from .config import settings

class Base(DeclarativeBase):
    pass



# Add new databases here

_engines: dict = {}
_session_factories: dict = {}

_mongo_client: AsyncMongoClient | None = None

def init_engines() -> None:
    """Create all database engines. Called once at app startup (lifespan)."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncMongoClient(settings.MONGODB_URL)

    if "places" in _engines:
        return
    _engines["places"] = create_async_engine(
        settings.PLACES_DB_URL,
        pool_size=40,
        max_overflow=60,
        pool_timeout=60.0,
        # Detects dropped connections before handing them to a handler
        pool_pre_ping=True,
        # Proactively recycle connections before RDS's idle timeout
        pool_recycle=1800,
        echo=settings.ENVIRONMENT == "development",
    )
    _session_factories["places"] = async_sessionmaker(
        _engines["places"], expire_on_commit=False
    )


async def close_engines() -> None:
    """Dispose all engine connection pools. Called at app shutdown (lifespan)."""
    global _mongo_client
    if _mongo_client is not None:
        await _mongo_client.close()

    for engine in _engines.values():
        await engine.dispose()



# FastAPI dependency helpers
async def get_places_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factories["places"]() as session:
        yield session


# Typed alias for imports
PlacesDB = Annotated[AsyncSession, Depends(get_places_db)]


async def get_mongo_db() -> AsyncGenerator[AsyncDatabase, None]:
    # We implicitly default to a database named "cyclelink" inside the Mongo cluster
    yield _mongo_client.cyclelink

MongoDB = Annotated[AsyncDatabase, Depends(get_mongo_db)]
