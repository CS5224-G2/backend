"""
Auth service — password hashing, JWT, refresh token lifecycle, register/authenticate flows.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
import bcrypt as _bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import PasswordResetToken, RefreshToken, User

# ============================================================
# Password helpers
# ============================================================

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ============================================================
# JWT helpers
# ============================================================

def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    """Returns (encoded_jwt, expires_in_seconds)."""
    expires_in = settings.JWT_EXPIRE_MINUTES * 60
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    """Returns the decoded payload. Raises JWTError on invalid/expired token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ============================================================
# Refresh token helpers
# ============================================================

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def create_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    client: str,
    remember_me: bool,
) -> str:
    """Generates a raw opaque token, stores its SHA-256 hash, returns the raw token."""
    raw = secrets.token_urlsafe(64)
    expire_days = (
        settings.REFRESH_TOKEN_REMEMBER_ME_DAYS if remember_me
        else settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    record = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        client=client,
        remember_me=remember_me,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expire_days),
    )
    db.add(record)
    await db.commit()
    return raw


async def validate_and_rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
) -> tuple[User, str]:
    """
    Validates the token hash, checks expiry and revocation, then rotates:
    sets revoked_at on the old record and issues a new raw token.
    Returns (user, new_raw_token).
    Raises HTTP 401 on any failure.
    """
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if record is None or record.revoked_at is not None:
        raise _invalid
    if record.expires_at < datetime.now(timezone.utc):
        raise _invalid

    # Revoke old record
    record.revoked_at = datetime.now(timezone.utc)
    await db.flush()

    # Load the user
    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _invalid

    # Issue a new token with the same remember_me setting
    new_raw = await create_refresh_token(db, user.id, record.client, record.remember_me)
    return user, new_raw


async def revoke_all_user_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke all active refresh tokens for a user. Used on account deletion."""
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    for token in result.scalars().all():
        token.revoked_at = now
    await db.commit()


# ============================================================
# Auth flows
# ============================================================

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Fetches user by email and verifies password. Raises HTTP 401 on failure."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )
    return user


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """
    Generates a password reset token and sends it via SendGrid.
    Always returns silently even if the email is not registered (prevents user enumeration).
    """
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return

    raw = secrets.token_urlsafe(64)
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
    )
    db.add(record)
    await db.commit()

    from ..clients.http import sendgrid_client
    await sendgrid_client.post(
        "/v3/mail/send",
        json={
            "personalizations": [{"to": [{"email": user.email}]}],
            "from": {"email": settings.SENDGRID_FROM_EMAIL},
            "subject": "Reset your CycleLink password",
            "content": [{"type": "text/plain", "value": f"Your CycleLink password reset token is:\n\n{raw}\n\nEnter this token in the app to reset your password. It expires in {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes."}],
        },
    )


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """
    Validates a password reset token, updates the user's password, and marks the token as used.
    Raises HTTP 400 if the token is invalid, already used, or expired.
    """
    _invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )

    token_hash = _hash_token(token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if record is None or record.used_at is not None:
        raise _invalid
    if record.expires_at < datetime.now(timezone.utc):
        raise _invalid

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _invalid

    now = datetime.now(timezone.utc)
    record.used_at = now
    user.hashed_password = hash_password(new_password)
    user.updated_at = now
    await db.commit()


async def register_user(
    db: AsyncSession,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> User:
    """Creates a new user. Raises HTTP 409 if the email is already registered."""
    email = email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
