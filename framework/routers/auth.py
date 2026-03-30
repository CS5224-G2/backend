from fastapi import APIRouter, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import settings
from ..database import PlacesDB
from ..models import User
from ..schemas import AuthResponse, AuthUserResponse, LoginRequest, RegisterRequest, TokenRefreshRequest
from ..services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])
_limiter = Limiter(key_func=get_remote_address)


def _build_auth_response(user: User, access_token: str, refresh_token: str, expires_in: int) -> AuthResponse:
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=AuthUserResponse(
            id=str(user.id),
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            onboarding_complete=user.onboarding_complete,
            role=user.role.value,
        ),
    )

@router.post("/login")
@_limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(request: Request, body: LoginRequest, db: PlacesDB) -> AuthResponse:
    user = await auth_service.authenticate_user(db, body.email, body.password)
    access_token, expires_in = auth_service.create_access_token(str(user.id), user.role.value)
    refresh_token = await auth_service.create_refresh_token(
        db, user.id, body.client, body.remember_me
    )
    return _build_auth_response(user, access_token, refresh_token, expires_in)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: PlacesDB) -> AuthResponse:
    if not body.agreed_to_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must agree to the terms of service",
        )
    user = await auth_service.register_user(
        db, body.first_name, body.last_name, body.email, body.password
    )
    access_token, expires_in = auth_service.create_access_token(str(user.id), user.role.value)
    refresh_token = await auth_service.create_refresh_token(
        db, user.id, body.client, remember_me=False
    )
    return _build_auth_response(user, access_token, refresh_token, expires_in)


@router.post("/refresh")
async def refresh_token(body: TokenRefreshRequest, db: PlacesDB) -> AuthResponse:
    user, new_refresh_token = await auth_service.validate_and_rotate_refresh_token(
        db, body.refresh_token
    )
    access_token, expires_in = auth_service.create_access_token(str(user.id), user.role.value)
    return _build_auth_response(user, access_token, new_refresh_token, expires_in)