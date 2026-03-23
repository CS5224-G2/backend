from fastapi import APIRouter
from pydantic import BaseModel
from ..database import MongoDB

router = APIRouter(prefix="/notes", tags=["MongoDB Demo"])

class NoteModel(BaseModel):
    title: str
    content: str

@router.post("/")
async def create_note(note: NoteModel, db: MongoDB):
    # Insert a document into the 'notes' collection
    result = await db.notes.insert_one(note.model_dump())
    return {"id": str(result.inserted_id), "status": "created"}

@router.get("/")
async def get_notes(db: MongoDB):
    # Fetch all documents from the 'notes' collection
    cursor = db.notes.find({})
    notes = []
    async for document in cursor:
        notes.append({
            "id": str(document["_id"]),
            "title": document.get("title"),
            "content": document.get("content")
        })
    return notes
