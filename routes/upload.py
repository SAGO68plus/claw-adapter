"""Icon upload routes."""
import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter(prefix="/api/upload", tags=["upload"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MAX_SIZE = 2 * 1024 * 1024  # 2MB


@router.post("/icon")
async def upload_icon(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported format. Allowed: {', '.join(ALLOWED_EXT)}")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(400, "File too large (max 2MB)")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    fname = f"{uuid.uuid4().hex[:12]}{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    with open(path, "wb") as f:
        f.write(data)
    return {"url": f"/uploads/{fname}"}
