from fastapi import APIRouter

from ..database import PlacesDB
from ..dependencies import AdminUser
from ..schemas import AdminUserListItem
from ..services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users")
async def list_users(admin: AdminUser, db: PlacesDB) -> list[AdminUserListItem]:
    users = await admin_service.get_all_users(db)
    return [admin_service.format_admin_user(u) for u in users]


@router.get("/stats")
async def get_stats(admin: AdminUser, db: PlacesDB) -> dict:
    active_users = await admin_service.get_active_user_count(db)
    return {
        "total_rides": 0,
        "active_users": active_users,
        "revenue_formatted": "$0",
        "open_reports": 0,
    }
