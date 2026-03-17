from typing import AsyncGenerator, Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from .config import settings


class Base(DeclarativeBase):
    pass



# Add new databases here

_engines: dict = {}
_session_factories: dict = {}


def init_engines() -> None:
    """Create all database engines. Called once at app startup (lifespan)."""
    if "places" in _engines:
        return
    _engines["places"] = create_async_engine(
        settings.PLACES_DB_URL,
        pool_size=10,
        max_overflow=20,
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
    for engine in _engines.values():
        await engine.dispose()



# FastAPI dependency helpers
async def get_places_db() -> AsyncGenerator[AsyncSession, None]:
    async with _session_factories["places"]() as session:
        yield session


# Typed alias for imports
PlacesDB = Annotated[AsyncSession, Depends(get_places_db)]
