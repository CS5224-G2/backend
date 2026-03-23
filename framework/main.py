from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .clients.http import service_client
from .config import settings
from .database import close_engines, init_engines
from .routers import hawker, historic_sites, parks, tourist_attractions, route_suggestion, mongodb_test


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_engines()
    yield
    # Shutdown
    await close_engines()
    await service_client.aclose()


app = FastAPI(
    title="CycleLink API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
_V1 = "/v1"

app.include_router(hawker.router, prefix=_V1)
app.include_router(historic_sites.router, prefix=_V1)
app.include_router(parks.router, prefix=_V1)
app.include_router(tourist_attractions.router, prefix=_V1)
app.include_router(route_suggestion.router, prefix=_V1)
app.include_router(mongodb_test.router, prefix=_V1)
