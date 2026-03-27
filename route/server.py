from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from framework.config import settings
from framework.database import close_engines, init_engines
from framework.routers import route_suggestion

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    init_engines()
    yield
    # Shutdown
    await close_engines()

app = FastAPI(
    title="CycleLink Bike Route API",
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

app.include_router(route_suggestion.router, prefix=_V1)
