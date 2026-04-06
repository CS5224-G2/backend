from fastapi import APIRouter, Query, status
from typing import Literal

from ..database import MongoDB, PlacesDB
from ..dependencies import CurrentUser
from ..schemas import (
    CreateRideRequest,
    CreateRideResponse,
    DistanceStat,
    FeedbackRequest,
    RideDetailResponse,
    RideHistoryItem,
)
from ..services import feedback as feedback_service
from ..services import rides as rides_service

router = APIRouter(prefix="/rides", tags=["Rides"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateRideResponse)
async def create_ride(
    body: CreateRideRequest,
    current_user: CurrentUser,
    mongo: MongoDB,
):
    return await rides_service.create_ride(mongo, current_user.id, body)


@router.get("/history", response_model=list[RideHistoryItem])
async def get_ride_history(
    current_user: CurrentUser,
    db: PlacesDB,
    mongo: MongoDB,
):
    return await rides_service.get_ride_history(db, mongo, current_user.id)


@router.get("/stats/distance", response_model=list[DistanceStat])
async def get_distance_stats(
    current_user: CurrentUser,
    mongo: MongoDB,
    period: Literal["week", "month"] = Query(...),
):
    return await rides_service.get_distance_stats(mongo, current_user.id, period)


@router.get("/{ride_id}", response_model=RideDetailResponse)
async def get_ride_by_id(
    ride_id: str,
    current_user: CurrentUser,
    db: PlacesDB,
    mongo: MongoDB,
):
    return await rides_service.get_ride_by_id(db, mongo, current_user.id, ride_id)


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def post_feedback(
    body: FeedbackRequest,
    current_user: CurrentUser,
    db: PlacesDB,
    mongo: MongoDB,
):
    await feedback_service.submit_feedback(db, mongo, current_user.id, body)
