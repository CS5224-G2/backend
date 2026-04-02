import uuid
import logging

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import UserRouteRating
from ..schemas import FeedbackRequest

logger = logging.getLogger(__name__)

_PRECOMPUTED_COLLECTION = "precomputed-routes"
_GENERATED_COLLECTION = "generated-routes"


async def _find_route_doc(mongo: AsyncDatabase, route_id: str) -> dict | None:
    """Return the raw MongoDB document for a route, or None if not found."""
    try:
        oid = ObjectId(route_id)
    except Exception:
        return None

    doc = await mongo[_PRECOMPUTED_COLLECTION].find_one({"_id": oid})
    if doc is not None:
        return doc

    return await mongo[_GENERATED_COLLECTION].find_one({"_id": oid})


async def submit_feedback(
    db: AsyncSession,
    mongo: AsyncDatabase,
    user_id: uuid.UUID,
    body: FeedbackRequest,
) -> None:
    # 1. Verify route exists in MongoDB
    route_doc = await _find_route_doc(mongo, body.route_id)
    if route_doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")

    # 2. Upsert rating in PostgreSQL
    result = await db.execute(
        select(UserRouteRating).where(
            UserRouteRating.user_id == user_id,
            UserRouteRating.route_id == body.route_id,
        )
    )
    record = result.scalar_one_or_none()
    if record:
        record.rating = body.rating
        record.review_text = body.review_text or None
    else:
        record = UserRouteRating(
            user_id=user_id,
            route_id=body.route_id,
            rating=body.rating,
            review_text=body.review_text or None,
        )
        db.add(record)
    await db.commit()

    # 3. Recompute aggregate across all ratings for this route
    agg = await db.execute(
        select(func.count(), func.avg(UserRouteRating.rating)).where(
            UserRouteRating.route_id == body.route_id
        )
    )
    count, avg = agg.one()
    new_count = count or 0
    new_avg = round(float(avg), 2) if avg else 0.0

    # 4. Write updated aggregates back to the route document in MongoDB
    collection = _PRECOMPUTED_COLLECTION if route_doc.get("source") == "precomputed" else _GENERATED_COLLECTION
    await mongo[collection].update_one(
        {"_id": route_doc["_id"]},
        {"$set": {"review_count": new_count, "rating": new_avg}},
    )
    logger.info(
        "Feedback submitted — route_id=%s user_id=%s rating=%d new_avg=%.2f count=%d",
        body.route_id, user_id, body.rating, new_avg, new_count,
    )
