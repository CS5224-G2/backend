"""
Admin service — user listing and stats stubs.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pymongo.asynchronous.database import AsyncDatabase

from ..models import User, UserRouteRating
from ..schemas import AdminUserListItem


async def get_all_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_active_user_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).where(User.is_active.is_(True)))
    return result.scalar_one()


def format_admin_user(user: User) -> AdminUserListItem:
    return AdminUserListItem(
        user_id=str(user.id),
        email_address=user.email,
        role=user.role.value,
        account_status="Active" if user.is_active else "Inactive",
        joined_formatted=user.created_at.strftime("%b %Y"),
    )


async def get_routing_quality_metrics(db: AsyncSession, mongo: AsyncDatabase) -> dict:
    """
    Aggregate routing quality signals for the admin dashboard:
    - Overall average rating and review count from PostgreSQL
    - Top-rated routes and most-reviewed routes from MongoDB
    - Total rides logged from MongoDB (ride completion proxy)
    """
    # PostgreSQL: overall rating stats
    agg = await db.execute(
        select(func.count(), func.avg(UserRouteRating.rating))
    )
    total_reviews, overall_avg_rating = agg.one()
    total_reviews = total_reviews or 0
    overall_avg_rating = round(float(overall_avg_rating), 2) if overall_avg_rating else None

    # MongoDB: top-rated routes (min 3 reviews for statistical significance)
    top_rated_cursor = mongo["precomputed-routes"].find(
        {"review_count": {"$gte": 3}},
        {"_id": 1, "name": 1, "rating": 1, "review_count": 1},
    ).sort("rating", -1).limit(5)
    top_rated = []
    async for doc in top_rated_cursor:
        top_rated.append({
            "route_id": str(doc["_id"]),
            "name": doc.get("name", "Unnamed"),
            "rating": doc.get("rating", 0),
            "review_count": doc.get("review_count", 0),
        })

    # MongoDB: most-reviewed routes
    most_reviewed_cursor = mongo["precomputed-routes"].find(
        {"review_count": {"$gt": 0}},
        {"_id": 1, "name": 1, "rating": 1, "review_count": 1},
    ).sort("review_count", -1).limit(5)
    most_reviewed = []
    async for doc in most_reviewed_cursor:
        most_reviewed.append({
            "route_id": str(doc["_id"]),
            "name": doc.get("name", "Unnamed"),
            "rating": doc.get("rating", 0),
            "review_count": doc.get("review_count", 0),
        })

    # MongoDB: total completed rides
    total_rides = await mongo["user-rides"].count_documents({})

    return {
        "total_reviews": total_reviews,
        "overall_avg_rating": overall_avg_rating,
        "total_rides_logged": total_rides,
        "top_rated_routes": top_rated,
        "most_reviewed_routes": most_reviewed,
    }
