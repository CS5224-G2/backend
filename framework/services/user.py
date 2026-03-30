"""
User service — profile CRUD, S3 avatar upload/delete, account deletion, password change, privacy.
"""
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import CyclingPreference, User, UserSavedRoute
from ..schemas import (
    PrivacyControls,
    RideStats,
    UpdateProfileRequest,
    UserProfileResponse,
)
from .auth import verify_password, hash_password

_ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}

MAX_AVATAR_BYTES = 10 * 1024 * 1024  # 10 MB


# ============================================================
# S3 client (module-level singleton)
# ============================================================

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )
    return _s3_client


def _avatar_s3_key(user_id: uuid.UUID, ext: str) -> str:
    return f"profile/{user_id}/avatar.{ext}"


def _avatar_url(s3_key: str) -> str:
    if settings.CDN_BASE_URL:
        return f"{settings.CDN_BASE_URL.rstrip('/')}/{s3_key}"
    return f"https://{settings.S3_USER_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"


# ============================================================
# DB helpers
# ============================================================

async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ============================================================
# Profile
# ============================================================

async def get_saved_route_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(UserSavedRoute).where(UserSavedRoute.user_id == user_id)
    )
    return len(result.scalars().all())


async def build_profile_response(db: AsyncSession, user: User) -> UserProfileResponse:
    saved_count = await get_saved_route_count(db, user.id)
    return UserProfileResponse(
        user_id=str(user.id),
        full_name=f"{user.first_name} {user.last_name}",
        email_address=user.email,
        city_name=user.city_name,
        member_since=user.created_at.strftime("%B %Y"),
        cycling_preference=user.cycling_preference.value if user.cycling_preference else None,
        weekly_goal_km=user.weekly_goal_km,
        bio_text=user.bio_text,
        avatar_url=user.avatar_url,
        avatar_color=user.avatar_color,
        ride_stats=RideStats(favorite_trails_count=saved_count),
    )


async def update_user_profile(
    db: AsyncSession,
    user: User,
    data: UpdateProfileRequest,
) -> User:
    if data.full_name is not None:
        first, _, rest = data.full_name.strip().partition(" ")
        user.first_name = first
        user.last_name = rest or first  # single-word name edge case
    if data.city_name is not None:
        user.city_name = data.city_name
    if data.cycling_preference is not None:
        user.cycling_preference = CyclingPreference(data.cycling_preference)
    if data.weekly_goal_km is not None:
        user.weekly_goal_km = data.weekly_goal_km
    if data.bio_text is not None:
        user.bio_text = data.bio_text
    if data.avatar_color is not None:
        user.avatar_color = data.avatar_color

    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================
# Password change
# ============================================================

async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> datetime:
    """Verifies current password, sets new hash. Returns updated_at timestamp."""
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    user.hashed_password = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user.updated_at


# ============================================================
# Privacy
# ============================================================

async def update_privacy(
    db: AsyncSession,
    user: User,
    controls: PrivacyControls,
) -> User:
    user.third_party_ads_opt_out = controls.third_party_ads_opt_out
    user.data_improvement_opt_out = controls.data_improvement_opt_out
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


# ============================================================
# Avatar
# ============================================================

async def upload_avatar(
    db: AsyncSession,
    user: User,
    file_bytes: bytes,
    content_type: str,
) -> str:
    """Uploads image to S3, updates user.avatar_url, returns the URL."""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported media type. Allowed: {', '.join(_ALLOWED_IMAGE_TYPES)}",
        )
    ext = _ALLOWED_IMAGE_TYPES[content_type]
    s3_key = _avatar_s3_key(user.id, ext)

    _get_s3().put_object(
        Bucket=settings.S3_USER_BUCKET,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )

    url = _avatar_url(s3_key)
    user.avatar_url = url
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return url


async def delete_avatar(db: AsyncSession, user: User) -> None:
    """Deletes avatar from S3 and clears user.avatar_url. Raises 404 if none exists."""
    if not user.avatar_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No avatar exists for this user",
        )

    # Derive the S3 key from the current avatar_url
    # Supports both CDN URLs and direct S3 URLs
    if settings.CDN_BASE_URL and user.avatar_url.startswith(settings.CDN_BASE_URL):
        s3_key = user.avatar_url[len(settings.CDN_BASE_URL.rstrip("/")) + 1:]
    else:
        # Direct S3 URL: https://{bucket}.s3.{region}.amazonaws.com/{key}
        prefix = f"https://{settings.S3_USER_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/"
        s3_key = user.avatar_url[len(prefix):]

    try:
        _get_s3().delete_object(Bucket=settings.S3_USER_BUCKET, Key=s3_key)
    except ClientError:
        pass

    user.avatar_url = None
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()


# ============================================================
# Account deletion
# ============================================================

async def delete_account(db: AsyncSession, user: User) -> None:
    """
    Deletes user's avatar from S3 if present, then hard-deletes the User row.
    ON DELETE CASCADE in the DB handles refresh_tokens automatically.
    """
    if user.avatar_url:
        try:
            await delete_avatar(db, user)
        except HTTPException:
            pass  # 404 on avatar is fine during deletion

    await db.delete(user)
    await db.commit()
