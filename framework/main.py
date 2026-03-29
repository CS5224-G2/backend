import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .clients.http import service_client
from .config import settings
from .database import close_engines, init_engines
from .routers import hawker, historic_sites, parks, tourist_attractions, route_suggestion, routes, mongodb_test, weather

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
async def lifespan(app: FastAPI):
    # Startup
    init_engines()
    _load_osm_graph()
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
app.include_router(routes.router, prefix=_V1)
app.include_router(mongodb_test.router, prefix=_V1)
app.include_router(weather.router, prefix=_V1)
