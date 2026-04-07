from fastapi import APIRouter

from ..database import PlacesDB, MongoDB
from ..dependencies import AdminUser
from ..schemas import AdminUserListItem
from ..services import admin as admin_service
from ..services import cloudwatch as cw_service
from ..services import health as health_service

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


@router.get("/infrastructure-metrics")
async def get_infrastructure_metrics(admin: AdminUser) -> dict:
    return await cw_service.get_infrastructure_metrics()


@router.get("/infrastructure-logs")
async def get_infrastructure_logs(admin: AdminUser) -> dict:
    return await cw_service.get_recent_error_logs()


@router.get("/infrastructure-health")
async def get_infrastructure_health(admin: AdminUser, places_db: PlacesDB, mongo_db: MongoDB) -> dict:
    return await health_service.get_system_health(places_db, mongo_db)


@router.get("/routing-quality-metrics")
async def get_routing_quality_metrics(admin: AdminUser, db: PlacesDB, mongo_db: MongoDB) -> dict:
    return await admin_service.get_routing_quality_metrics(db, mongo_db)
