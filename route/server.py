import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from framework.config import settings
from framework.database import close_engines, init_engines
from framework.routers import route_suggestion, routes

logger = logging.getLogger(__name__)


def _load_osm_graph():
    """Load the pre-downloaded Singapore OSM graph into memory on startup."""
    from bike_route.graph_manager import load_graph_from_s3, load_graph_from_file

    if settings.OSM_GRAPH_LOCAL_PATH:
        load_graph_from_file(settings.OSM_GRAPH_LOCAL_PATH)
    elif settings.S3_BUCKET_NAME:
        load_graph_from_s3(
            settings.S3_BUCKET_NAME,
            settings.OSM_GRAPH_S3_KEY or None,
        )
    else:
        logger.warning(
            "No OSM graph configured (set S3_BUCKET_NAME or OSM_GRAPH_LOCAL_PATH). "
            "Falling back to live Overpass API calls per request."
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    init_engines()
    _load_osm_graph()
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
app.include_router(routes.router, prefix=_V1)
