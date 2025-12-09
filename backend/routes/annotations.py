"""
Clip annotation routes.

Provides endpoints for managing clip annotations (drawings and audio).
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional
import uuid
import os

from backend.models.annotation import (
    AnnotationData,
    AnnotationResponse
)
from backend.auth import get_current_user
from backend.auth.dependencies import db_pool, require_coach

router = APIRouter(prefix="/clips", tags=["Clip Annotations"])

# MinIO configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
BUCKET_NAME = "basketball-clips"


def get_minio_client():
    from minio import Minio
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )


@router.get("/{clip_id}/annotations", response_model=Optional[AnnotationResponse])
async def get_annotations(
    clip_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get annotations for a clip.

    Anyone with clip access can view annotations.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, clip_id, created_by, drawing_data, audio_path,
                   version, created_at, updated_at
            FROM clip_annotations
            WHERE clip_id = $1
            ORDER BY version DESC
            LIMIT 1
            """,
            uuid.UUID(clip_id)
        )

        if not row:
            return None

    return AnnotationResponse(
        id=str(row["id"]),
        clip_id=str(row["clip_id"]),
        created_by=str(row["created_by"]) if row["created_by"] else None,
        drawing_data=row["drawing_data"],
        audio_path=row["audio_path"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.post("/{clip_id}/annotations", response_model=AnnotationResponse, status_code=status.HTTP_201_CREATED)
async def save_annotations(
    clip_id: str,
    data: AnnotationData,
    current_user: dict = Depends(require_coach())
):
    """
    Save or update clip annotations.

    Only coaches can create/update annotations.
    """
    async with db_pool.acquire() as conn:
        # Verify clip exists
        clip_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM clips WHERE id = $1)",
            uuid.UUID(clip_id)
        )

        if not clip_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clip not found"
            )

        # Check for existing annotation
        existing = await conn.fetchrow(
            "SELECT id, version FROM clip_annotations WHERE clip_id = $1 ORDER BY version DESC LIMIT 1",
            uuid.UUID(clip_id)
        )

        if existing:
            # Update existing
            row = await conn.fetchrow(
                """
                UPDATE clip_annotations
                SET drawing_data = $1, updated_at = NOW()
                WHERE id = $2
                RETURNING id, clip_id, created_by, drawing_data, audio_path,
                          version, created_at, updated_at
                """,
                data.drawing_data, existing["id"]
            )
        else:
            # Create new
            row = await conn.fetchrow(
                """
                INSERT INTO clip_annotations (clip_id, created_by, drawing_data)
                VALUES ($1, $2, $3)
                RETURNING id, clip_id, created_by, drawing_data, audio_path,
                          version, created_at, updated_at
                """,
                uuid.UUID(clip_id), uuid.UUID(current_user["id"]), data.drawing_data
            )

    return AnnotationResponse(
        id=str(row["id"]),
        clip_id=str(row["clip_id"]),
        created_by=str(row["created_by"]) if row["created_by"] else None,
        drawing_data=row["drawing_data"],
        audio_path=row["audio_path"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"]
    )


@router.post("/{clip_id}/audio", status_code=status.HTTP_201_CREATED)
async def upload_audio_overlay(
    clip_id: str,
    audio: UploadFile = File(...),
    current_user: dict = Depends(require_coach())
):
    """
    Upload audio overlay for a clip.

    Only coaches can upload audio.
    """
    async with db_pool.acquire() as conn:
        # Get or create annotation
        annotation = await conn.fetchrow(
            "SELECT id FROM clip_annotations WHERE clip_id = $1 ORDER BY version DESC LIMIT 1",
            uuid.UUID(clip_id)
        )

        if not annotation:
            annotation = await conn.fetchrow(
                """
                INSERT INTO clip_annotations (clip_id, created_by)
                VALUES ($1, $2)
                RETURNING id
                """,
                uuid.UUID(clip_id), uuid.UUID(current_user["id"])
            )

        # Upload audio to MinIO
        audio_path = f"annotations/{clip_id}/audio_{uuid.uuid4()}.webm"
        temp_file = f"/tmp/{uuid.uuid4()}.webm"

        with open(temp_file, "wb") as f:
            content = await audio.read()
            f.write(content)

        try:
            minio_client = get_minio_client()
            minio_client.fput_object(BUCKET_NAME, audio_path, temp_file)
        finally:
            os.remove(temp_file)

        # Update annotation with audio path
        await conn.execute(
            "UPDATE clip_annotations SET audio_path = $1, updated_at = NOW() WHERE id = $2",
            audio_path, annotation["id"]
        )

    return {"audio_path": audio_path, "message": "Audio uploaded successfully"}


@router.get("/{clip_id}/audio")
async def get_audio_overlay(
    clip_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Stream audio overlay for a clip.
    """
    async with db_pool.acquire() as conn:
        audio_path = await conn.fetchval(
            "SELECT audio_path FROM clip_annotations WHERE clip_id = $1 AND audio_path IS NOT NULL ORDER BY version DESC LIMIT 1",
            uuid.UUID(clip_id)
        )

        if not audio_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No audio overlay found"
            )

    minio_client = get_minio_client()
    try:
        response = minio_client.get_object(BUCKET_NAME, audio_path)
        return StreamingResponse(
            response.stream(),
            media_type="audio/webm"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found"
        )


@router.delete("/{clip_id}/audio", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audio_overlay(
    clip_id: str,
    current_user: dict = Depends(require_coach())
):
    """
    Delete audio overlay for a clip.

    Only coaches can delete audio.
    """
    async with db_pool.acquire() as conn:
        audio_path = await conn.fetchval(
            "SELECT audio_path FROM clip_annotations WHERE clip_id = $1 AND audio_path IS NOT NULL ORDER BY version DESC LIMIT 1",
            uuid.UUID(clip_id)
        )

        if not audio_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No audio overlay found"
            )

        # Delete from MinIO
        minio_client = get_minio_client()
        try:
            minio_client.remove_object(BUCKET_NAME, audio_path)
        except:
            pass

        # Update annotation
        await conn.execute(
            "UPDATE clip_annotations SET audio_path = NULL, updated_at = NOW() WHERE clip_id = $1",
            uuid.UUID(clip_id)
        )
