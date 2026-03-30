from fastapi import APIRouter, File, HTTPException, UploadFile, status

from ..database import PlacesDB
from ..dependencies import CurrentUser
from ..schemas import (
    AvatarUploadResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    DevicePermissions,
    PrivacyControls,
    PrivacyResponse,
    UpdatePrivacyRequest,
    UpdateProfileRequest,
    UserProfileResponse,
)
from ..services import user as user_service

router = APIRouter(prefix="/user", tags=["User"])

_MAX_AVATAR_BYTES = 10 * 1024 * 1024  # 10 MB


@router.get("/profile")
async def get_profile(current_user: CurrentUser, db: PlacesDB) -> UserProfileResponse:
    return await user_service.build_profile_response(db, current_user)


@router.put("/profile")
async def update_profile(
    body: UpdateProfileRequest,
    current_user: CurrentUser,
    db: PlacesDB,
) -> UserProfileResponse:
    updated = await user_service.update_user_profile(db, current_user, body)
    return await user_service.build_profile_response(db, updated)


@router.post("/profile/avatar", status_code=201)
async def upload_avatar(
    current_user: CurrentUser,
    db: PlacesDB,
    avatar: UploadFile = File(...),
) -> AvatarUploadResponse:
    file_bytes = await avatar.read(_MAX_AVATAR_BYTES + 1)
    if len(file_bytes) > _MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 10 MB limit",
        )
    url = await user_service.upload_avatar(db, current_user, file_bytes, avatar.content_type or "")
    return AvatarUploadResponse(avatar_url=url)


@router.delete("/profile/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(current_user: CurrentUser, db: PlacesDB) -> None:
    await user_service.delete_avatar(db, current_user)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(current_user: CurrentUser, db: PlacesDB) -> None:
    await user_service.delete_account(db, current_user)


@router.post("/password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    db: PlacesDB,
) -> ChangePasswordResponse:
    updated_at = await user_service.change_password(
        db, current_user, body.current_password, body.new_password
    )
    return ChangePasswordResponse(updated_at=updated_at.isoformat())


@router.get("/privacy")
async def get_privacy(current_user: CurrentUser) -> PrivacyResponse:
    return PrivacyResponse(
        privacy_controls=PrivacyControls(
            third_party_ads_opt_out=current_user.third_party_ads_opt_out,
            data_improvement_opt_out=current_user.data_improvement_opt_out,
        ),
        device_permissions=DevicePermissions(),
    )


@router.put("/privacy")
async def update_privacy(
    body: UpdatePrivacyRequest,
    current_user: CurrentUser,
    db: PlacesDB,
) -> PrivacyResponse:
    updated = await user_service.update_privacy(db, current_user, body.privacy_controls)
    return PrivacyResponse(
        privacy_controls=PrivacyControls(
            third_party_ads_opt_out=updated.third_party_ads_opt_out,
            data_improvement_opt_out=updated.data_improvement_opt_out,
        ),
        device_permissions=DevicePermissions(),
    )
