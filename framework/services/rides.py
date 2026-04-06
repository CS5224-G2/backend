import uuid
import logging
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import UserRouteRating
from ..schemas import (
    Checkpoint,
    CreateRideRequest,
    CreateRideResponse,
    DistanceStat,
    POIVisited,
    RideDetailResponse,
    RideHistoryItem,
)

logger = logging.getLogger(__name__)

_PRECOMPUTED_COLLECTION = "precomputed-routes"
_GENERATED_COLLECTION = "generated-routes"
_RIDES_COLLECTION = "user-rides"

_WEEK_DAYS = [
    ("mon", "Mon"),
    ("tue", "Tue"),
    ("wed", "Wed"),
    ("thu", "Thu"),
    ("fri", "Fri"),
    ("sat", "Sat"),
    ("sun", "Sun"),
]

_MONTH_WEEKS = [
    ("week1", "Week 1"),
    ("week2", "Week 2"),
    ("week3", "Week 3"),
    ("week4", "Week 4"),
]


async def _find_route_doc(mongo: AsyncDatabase, route_id: str) -> dict | None:
    try:
        oid = ObjectId(route_id)
    except Exception:
        return None

    doc = await mongo[_PRECOMPUTED_COLLECTION].find_one({"_id": oid})
    if doc is not None:
        return doc
    return await mongo[_GENERATED_COLLECTION].find_one({"_id": oid})


def _fmt_date(dt: datetime) -> str:
    """'March 28, 2026'"""
    return dt.strftime("%-d %B %Y").lstrip("0")


def _fmt_time(dt: datetime) -> str:
    """'10:30 AM'"""
    return dt.strftime("%-I:%M %p")


async def create_ride(
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
    body: CreateRideRequest,
) -> CreateRideResponse:
    route_doc = await _find_route_doc(mongo, body.route_id)
    if route_doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    route_name: str = route_doc.get("name") or body.route_id
    total_time = max(1, int((body.end_time - body.start_time).total_seconds() / 60))
    now = datetime.now(timezone.utc)

    doc = {
        "user_id": str(user_id),
        "route_id": body.route_id,
        "route_name": route_name,
        "start_time": body.start_time.astimezone(timezone.utc),
        "end_time": body.end_time.astimezone(timezone.utc),
        "total_time": total_time,
        "distance": body.distance,
        "avg_speed": body.avg_speed,
        "checkpoints_visited_count": len(body.checkpoints_visited),
        "checkpoints": [c.model_dump() for c in body.checkpoints_visited],
        "points_of_interest_visited": [p.model_dump() for p in body.points_of_interest_visited],
        "created_at": now,
    }
    result = await mongo[_RIDES_COLLECTION].insert_one(doc)

    end_utc = body.end_time.astimezone(timezone.utc)

    return CreateRideResponse(
        ride_id=str(result.inserted_id),
        route_id=body.route_id,
        route_name=route_name,
        completion_date=_fmt_date(end_utc),
        completion_time=_fmt_time(end_utc),
        start_time=body.start_time.isoformat(),
        end_time=body.end_time.isoformat(),
        total_time=total_time,
        distance=body.distance,
        avg_speed=body.avg_speed,
        checkpoints_visited=len(body.checkpoints_visited),
    )


async def get_ride_history(
    db: AsyncSession,
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
) -> list[RideHistoryItem]:
    cursor = mongo[_RIDES_COLLECTION].find({"user_id": str(user_id)}).sort("end_time", -1)
    rides = await cursor.to_list(length=None)

    if not rides:
        return []

    # Batch-fetch ratings for all route_ids in one query
    route_ids = list({r["route_id"] for r in rides})
    ratings_result = await db.execute(
        select(UserRouteRating).where(
            UserRouteRating.user_id == user_id,
            UserRouteRating.route_id.in_(route_ids),
        )
    )
    rating_map: dict[str, tuple[int, str | None]] = {
        rr.route_id: (rr.rating, rr.review_text)
        for rr in ratings_result.scalars().all()
    }

    items = []
    for ride in rides:
        rating_entry = rating_map.get(ride["route_id"])
        end_utc = ride["end_time"].replace(tzinfo=timezone.utc)
        start_utc = ride["start_time"].replace(tzinfo=timezone.utc)
        items.append(RideHistoryItem(
            ride_id=str(ride["_id"]),
            route_id=ride["route_id"],
            route_name=ride["route_name"],
            completion_date=_fmt_date(end_utc),
            completion_time=_fmt_time(end_utc),
            start_time=_fmt_time(start_utc),
            end_time=_fmt_time(end_utc),
            total_time=ride["total_time"],
            distance=ride["distance"],
            avg_speed=ride["avg_speed"],
            checkpoints_visited=ride["checkpoints_visited_count"],
            checkpoints=[Checkpoint(**c) for c in (ride.get("checkpoints") or [])],
            points_of_interest_visited=[POIVisited(**p) for p in (ride.get("points_of_interest_visited") or [])],
            rating=rating_entry[0] if rating_entry else None,
            review=rating_entry[1] if rating_entry else None,
        ))
    return items


async def get_ride_by_id(
    db: AsyncSession,
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
    ride_id: str,
) -> RideDetailResponse:
    from .routes import get_route_by_id

    try:
        oid = ObjectId(ride_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")

    ride = await mongo[_RIDES_COLLECTION].find_one({"_id": oid, "user_id": str(user_id)})
    if ride is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")

    rating_result = await db.execute(
        select(UserRouteRating).where(
            UserRouteRating.user_id == user_id,
            UserRouteRating.route_id == ride["route_id"],
        )
    )
    rating_record = rating_result.scalar_one_or_none()

    route_detail = await get_route_by_id(mongo, ride["route_id"])

    end_utc = ride["end_time"].replace(tzinfo=timezone.utc)
    start_utc = ride["start_time"].replace(tzinfo=timezone.utc)

    return RideDetailResponse(
        ride_id=str(ride["_id"]),
        route_id=ride["route_id"],
        route_name=ride["route_name"],
        completion_date=_fmt_date(end_utc),
        completion_time=_fmt_time(end_utc),
        start_time=_fmt_time(start_utc),
        end_time=_fmt_time(end_utc),
        total_time=ride["total_time"],
        distance=ride["distance"],
        avg_speed=ride["avg_speed"],
        checkpoints_visited=ride["checkpoints_visited_count"],
        checkpoints=[Checkpoint(**c) for c in (ride.get("checkpoints") or [])],
        points_of_interest_visited=[POIVisited(**p) for p in (ride.get("points_of_interest_visited") or [])],
        rating=rating_record.rating if rating_record else None,
        review=rating_record.review_text if rating_record else None,
        route_details=route_detail,
    )


async def get_distance_stats(
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
    period: str,
) -> list[DistanceStat]:
    now = datetime.now(timezone.utc)

    if period == "week":
        monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = monday + timedelta(days=7)
        window_start, window_end = monday, sunday
    else:  # month
        window_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        window_end = now + timedelta(days=1)

    cursor = mongo[_RIDES_COLLECTION].find({
        "user_id": str(user_id),
        "end_time": {"$gte": window_start, "$lt": window_end},
    })
    rides = await cursor.to_list(length=None)

    if period == "week":
        buckets: dict[int, float] = {i: 0.0 for i in range(7)}
        for ride in rides:
            day_idx = ride["end_time"].replace(tzinfo=timezone.utc).weekday()
            buckets[day_idx] = round(buckets[day_idx] + ride["distance"], 2)
        return [
            DistanceStat(period_id=pid, label=label, distance=buckets[i])
            for i, (pid, label) in enumerate(_WEEK_DAYS)
        ]
    else:
        buckets_month: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        for ride in rides:
            day = ride["end_time"].replace(tzinfo=timezone.utc).day
            week_num = min(4, (day - 1) // 7 + 1)
            buckets_month[week_num] = round(buckets_month[week_num] + ride["distance"], 2)
        return [
            DistanceStat(period_id=pid, label=label, distance=buckets_month[i + 1])
            for i, (pid, label) in enumerate(_MONTH_WEEKS)
        ]
