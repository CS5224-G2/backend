from fastapi import APIRouter, status

from ..database import MongoDB, PlacesDB
from ..dependencies import CurrentUser
from ..schemas import FeedbackRequest
from ..services import feedback as feedback_service

router = APIRouter(prefix="/rides", tags=["Rides"])


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def post_feedback(
    body: FeedbackRequest,
    current_user: CurrentUser,
    db: PlacesDB,
    mongo: MongoDB,
):
    await feedback_service.submit_feedback(db, mongo, current_user.id, body)
