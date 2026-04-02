"""
Shared FastAPI dependencies — current user resolution and role guards.
Import CurrentUser / AdminUser in routers.
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from jose import JWTError

from .database import PlacesDB
from .models import User, UserRole
from .services.auth import decode_access_token
from .services.user import get_user_by_id

# Supporting two options in Swagger for convenience:
# 1. Standard OAuth2 flow (but requires form data - will fail with JSON login)
# 2. HTTP Bearer (allows pasting a token manually - works even with JSON login)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    oauth2_token: Annotated[str | None, Depends(oauth2_scheme)],
    bearer_auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: PlacesDB,
) -> User:
    # Use one or the other
    token = oauth2_token or (bearer_auth.credentials if bearer_auth else None)
    if not token:
        raise _credentials_exception
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise _credentials_exception
    except JWTError:
        raise _credentials_exception

    user = await get_user_by_id(db, uuid.UUID(user_id_str))
    if user is None or not user.is_active:
        raise _credentials_exception
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_business(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.admin, UserRole.business):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Business access required"
        )
    return current_user


# Typed aliases — use these in router function signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
BusinessUser = Annotated[User, Depends(require_business)]
