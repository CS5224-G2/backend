import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .clients.http import service_client
from .config import settings
from .database import close_engines, init_engines
from .routers import (
    hawker,
    historic_sites,
    parks,
    route_suggestion,
    routes,
    tourist_attractions,
    weather,
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
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
    docs_url=None,   # Disable default docs
    redoc_url=None,
    openapi_url=None, # Secure openapi.json as well
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for prototype
    allow_credentials=False, # Must be False when using ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Swagger Security ---
security = HTTPBasic()


def authenticate_swagger(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, settings.SWAGGER_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, settings.SWAGGER_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/docs", include_in_schema=False)
async def get_swagger_ui(username: str = Depends(authenticate_swagger)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="CycleLink API - Swagger UI")


@app.get("/redoc", include_in_schema=False)
async def get_redoc(username: str = Depends(authenticate_swagger)):
    return get_redoc_html(openapi_url="/openapi.json", title="CycleLink API - ReDoc")


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(username: str = Depends(authenticate_swagger)):
    return JSONResponse(app.openapi())

@app.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "ok"}


# Routers
_V1 = "/v1"

app.include_router(hawker.router, prefix=_V1)
app.include_router(historic_sites.router, prefix=_V1)
app.include_router(parks.router, prefix=_V1)
app.include_router(tourist_attractions.router, prefix=_V1)
app.include_router(route_suggestion.router, prefix=_V1)
app.include_router(routes.router, prefix=_V1)
app.include_router(weather.router, prefix=_V1)
