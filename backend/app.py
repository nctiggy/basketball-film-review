from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import subprocess
import uuid
from datetime import datetime, date, timedelta
import asyncpg
from minio import Minio
from minio.error import S3Error
import asyncio
import json
from contextlib import asynccontextmanager

# Configuration from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://filmreview:filmreview@postgres:5432/filmreview")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_EXTERNAL_ENDPOINT = os.getenv("MINIO_EXTERNAL_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
BUCKET_NAME = "basketball-clips"

# Global database pool
db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    
    # Initialize MinIO client
    minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    
    # Create bucket if it doesn't exist
    try:
        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)
    except S3Error as e:
        print(f"Error creating bucket: {e}")
    
    # Initialize database schema
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                game_id UUID REFERENCES games(id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                video_path VARCHAR(500) NOT NULL,
                uploaded_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS clips (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                game_id UUID REFERENCES games(id) ON DELETE CASCADE,
                video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
                start_time VARCHAR(20) NOT NULL,
                end_time VARCHAR(20) NOT NULL,
                tags TEXT[] NOT NULL,
                notes TEXT,
                clip_path VARCHAR(500),
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
    
    yield
    
    # Shutdown
    await db_pool.close()

app = FastAPI(title="Basketball Film Review", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class GameCreate(BaseModel):
    name: str
    date: str

class Game(BaseModel):
    id: str
    name: str
    date: date
    created_at: datetime
    video_count: Optional[int] = 0

class Video(BaseModel):
    id: str
    game_id: str
    filename: str
    video_path: str
    uploaded_at: datetime

class ClipCreate(BaseModel):
    game_id: str
    video_id: str
    start_time: str
    end_time: str
    tags: List[str]
    notes: Optional[str] = None

class Clip(BaseModel):
    id: str
    game_id: str
    video_id: str
    start_time: str
    end_time: str
    tags: List[str]
    notes: Optional[str]
    clip_path: Optional[str]
    status: str
    created_at: datetime

# Helper functions
def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )

def get_minio_client_external():
    """Get MinIO client configured with external endpoint for presigned URLs"""
    return Minio(
        MINIO_EXTERNAL_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )

def time_to_seconds(time_str: str) -> str:
    """Convert mm:ss or hh:mm:ss to ffmpeg format"""
    parts = time_str.split(':')
    if len(parts) == 2:
        return f"00:{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    elif len(parts) == 3:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
    return time_str

async def stream_video_with_range(request: Request, object_path: str, minio_client: Minio) -> Response:
    """Stream video with support for HTTP Range requests for seeking/scrubbing"""
    try:
        # Get object metadata to know the file size
        stat = minio_client.stat_object(BUCKET_NAME, object_path)
        file_size = stat.size

        # Parse range header
        range_header = request.headers.get("range")

        if range_header:
            # Parse range header (format: "bytes=start-end")
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0
            end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1

            # Ensure end doesn't exceed file size
            end = min(end, file_size - 1)
            content_length = end - start + 1

            # Get the object with offset and length
            response_data = minio_client.get_object(
                BUCKET_NAME,
                object_path,
                offset=start,
                length=content_length
            )

            # Return 206 Partial Content
            return StreamingResponse(
                response_data.stream(),
                status_code=206,
                media_type="video/mp4",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(content_length),
                    "Content-Disposition": "inline"
                }
            )
        else:
            # No range header, return full file
            response_data = minio_client.get_object(BUCKET_NAME, object_path)
            return StreamingResponse(
                response_data.stream(),
                media_type="video/mp4",
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(file_size),
                    "Content-Disposition": "inline"
                }
            )
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f"Video not found: {str(e)}")

async def process_clip(clip_id: str, game_video_path: str, start_time: str, end_time: str):
    """Background task to extract video clip using ffmpeg"""
    try:
        # Update status to processing
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE clips SET status = 'processing' WHERE id = $1",
                uuid.UUID(clip_id)
            )
        
        # Download video from MinIO
        minio_client = get_minio_client()
        local_video_path = f"/tmp/{uuid.uuid4()}.mp4"
        minio_client.fget_object(BUCKET_NAME, game_video_path, local_video_path)
        
        # Convert time format
        start = time_to_seconds(start_time)
        end = time_to_seconds(end_time)
        
        # Extract clip
        output_path = f"/tmp/clip_{clip_id}.mp4"
        cmd = [
            "ffmpeg",
            "-i", local_video_path,
            "-ss", start,
            "-to", end,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-y",
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Upload clip to MinIO
        clip_minio_path = f"clips/{clip_id}.mp4"
        minio_client.fput_object(BUCKET_NAME, clip_minio_path, output_path)
        
        # Update database
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE clips SET status = 'completed', clip_path = $1 WHERE id = $2",
                clip_minio_path,
                uuid.UUID(clip_id)
            )
        
        # Cleanup
        os.remove(local_video_path)
        os.remove(output_path)
        
    except Exception as e:
        print(f"Error processing clip {clip_id}: {e}")
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE clips SET status = 'failed' WHERE id = $1",
                uuid.UUID(clip_id)
            )

# API Endpoints
@app.get("/")
async def root():
    return {"message": "Basketball Film Review API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/games", response_model=Game)
async def create_game(
    name: str = Form(...),
    date: str = Form(...)
):
    """Create a new game"""
    # Parse date string to date object
    try:
        game_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    game_id = str(uuid.uuid4())

    # Save to database
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO games (id, name, date)
            VALUES ($1, $2, $3)
            RETURNING id, name, date, created_at
            """,
            uuid.UUID(game_id), name, game_date
        )

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "date": row["date"],
        "created_at": row["created_at"],
        "video_count": 0
    }

@app.post("/games/{game_id}/videos", response_model=Video)
async def upload_video(
    game_id: str,
    video: UploadFile = File(...)
):
    """Upload a video for a game"""
    # Verify game exists
    async with db_pool.acquire() as conn:
        game = await conn.fetchrow("SELECT id FROM games WHERE id = $1", uuid.UUID(game_id))
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

    video_id = str(uuid.uuid4())
    video_path = f"games/{game_id}/{video_id}_{video.filename}"

    # Upload to MinIO
    minio_client = get_minio_client()
    temp_file = f"/tmp/{uuid.uuid4()}_{video.filename}"

    with open(temp_file, "wb") as f:
        content = await video.read()
        f.write(content)

    try:
        minio_client.fput_object(BUCKET_NAME, video_path, temp_file)
    finally:
        os.remove(temp_file)

    # Save to database
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO videos (id, game_id, filename, video_path)
            VALUES ($1, $2, $3, $4)
            RETURNING id, game_id, filename, video_path, uploaded_at
            """,
            uuid.UUID(video_id), uuid.UUID(game_id), video.filename, video_path
        )

    return {
        "id": str(row["id"]),
        "game_id": str(row["game_id"]),
        "filename": row["filename"],
        "video_path": row["video_path"],
        "uploaded_at": row["uploaded_at"]
    }

@app.get("/games/{game_id}/videos", response_model=List[Video])
async def list_game_videos(game_id: str):
    """List all videos for a game"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM videos WHERE game_id = $1 ORDER BY uploaded_at DESC",
            uuid.UUID(game_id)
        )

    return [
        {
            "id": str(row["id"]),
            "game_id": str(row["game_id"]),
            "filename": row["filename"],
            "video_path": row["video_path"],
            "uploaded_at": row["uploaded_at"]
        }
        for row in rows
    ]

@app.get("/videos/{video_id}", response_model=Video)
async def get_video(video_id: str):
    """Get a specific video"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM videos WHERE id = $1",
            uuid.UUID(video_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "id": str(row["id"]),
        "game_id": str(row["game_id"]),
        "filename": row["filename"],
        "video_path": row["video_path"],
        "uploaded_at": row["uploaded_at"]
    }

@app.put("/videos/{video_id}", response_model=Video)
async def update_video(
    video_id: str,
    filename: str = Form(...)
):
    """Update video metadata (filename only)"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE videos
            SET filename = $1
            WHERE id = $2
            RETURNING id, game_id, filename, video_path, uploaded_at
            """,
            filename, uuid.UUID(video_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Video not found")

    return {
        "id": str(row["id"]),
        "game_id": str(row["game_id"]),
        "filename": row["filename"],
        "video_path": row["video_path"],
        "uploaded_at": row["uploaded_at"]
    }

@app.delete("/videos/{video_id}")
async def delete_video(video_id: str):
    """Delete a video and all associated clips"""
    async with db_pool.acquire() as conn:
        # Get video path
        video = await conn.fetchrow(
            "SELECT video_path FROM videos WHERE id = $1",
            uuid.UUID(video_id)
        )

        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        # Get all clip paths to delete from MinIO
        clips = await conn.fetch(
            "SELECT clip_path FROM clips WHERE video_id = $1",
            uuid.UUID(video_id)
        )

        # Delete the video (cascades to clips in DB)
        await conn.execute(
            "DELETE FROM videos WHERE id = $1",
            uuid.UUID(video_id)
        )

    # Delete files from MinIO
    minio_client = get_minio_client()
    try:
        minio_client.remove_object(BUCKET_NAME, video["video_path"])
    except S3Error:
        pass

    for clip in clips:
        if clip["clip_path"]:
            try:
                minio_client.remove_object(BUCKET_NAME, clip["clip_path"])
            except S3Error:
                pass

    return {"message": "Video deleted successfully"}

@app.get("/games", response_model=List[Game])
async def list_games():
    """List all games"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT g.id, g.name, g.date, g.created_at, COUNT(v.id) as video_count
            FROM games g
            LEFT JOIN videos v ON g.id = v.game_id
            GROUP BY g.id, g.name, g.date, g.created_at
            ORDER BY g.date DESC
        """)

    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "date": row["date"],
            "created_at": row["created_at"],
            "video_count": row["video_count"]
        }
        for row in rows
    ]

@app.get("/games/{game_id}", response_model=Game)
async def get_game(game_id: str):
    """Get a specific game"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT g.id, g.name, g.date, g.created_at, COUNT(v.id) as video_count
            FROM games g
            LEFT JOIN videos v ON g.id = v.game_id
            WHERE g.id = $1
            GROUP BY g.id, g.name, g.date, g.created_at
            """,
            uuid.UUID(game_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Game not found")

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "date": row["date"],
        "created_at": row["created_at"],
        "video_count": row["video_count"]
    }

@app.put("/games/{game_id}", response_model=Game)
async def update_game(
    game_id: str,
    name: str = Form(...),
    date: str = Form(...)
):
    """Update a game"""
    try:
        game_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE games
            SET name = $1, date = $2
            WHERE id = $3
            RETURNING id, name, date, created_at
            """,
            name, game_date, uuid.UUID(game_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Game not found")

        # Get video count
        video_count = await conn.fetchval(
            "SELECT COUNT(*) FROM videos WHERE game_id = $1",
            uuid.UUID(game_id)
        )

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "date": row["date"],
        "created_at": row["created_at"],
        "video_count": video_count
    }

@app.delete("/games/{game_id}")
async def delete_game(game_id: str):
    """Delete a game and all associated videos and clips"""
    async with db_pool.acquire() as conn:
        # Get all video paths to delete from MinIO
        videos = await conn.fetch(
            "SELECT video_path FROM videos WHERE game_id = $1",
            uuid.UUID(game_id)
        )

        # Get all clip paths to delete from MinIO
        clips = await conn.fetch(
            "SELECT clip_path FROM clips WHERE game_id = $1",
            uuid.UUID(game_id)
        )

        # Delete the game (cascades to videos and clips in DB)
        result = await conn.execute(
            "DELETE FROM games WHERE id = $1",
            uuid.UUID(game_id)
        )

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Game not found")

    # Delete files from MinIO
    minio_client = get_minio_client()
    for video in videos:
        try:
            minio_client.remove_object(BUCKET_NAME, video["video_path"])
        except S3Error:
            pass

    for clip in clips:
        if clip["clip_path"]:
            try:
                minio_client.remove_object(BUCKET_NAME, clip["clip_path"])
            except S3Error:
                pass

    return {"message": "Game deleted successfully"}

@app.get("/games/{game_id}/video")
async def stream_game_video(game_id: str):
    """Stream the first video for a game"""
    # Get the first video for this game
    async with db_pool.acquire() as conn:
        video = await conn.fetchrow(
            "SELECT video_path FROM videos WHERE game_id = $1 ORDER BY uploaded_at ASC LIMIT 1",
            uuid.UUID(game_id)
        )

    if not video:
        raise HTTPException(status_code=404, detail="No videos found for this game")

    video_path = video["video_path"]
    # Use internal endpoint to connect to MinIO
    minio_client = get_minio_client()

    try:
        # Get presigned URL from MinIO (valid for 1 hour)
        url = minio_client.presigned_get_object(BUCKET_NAME, video_path, expires=timedelta(hours=1))
        # Replace internal endpoint with external endpoint for browser access
        url = url.replace(f"http://{MINIO_ENDPOINT}", f"http://{MINIO_EXTERNAL_ENDPOINT}")
        print(f"Generated presigned URL: {url}")
        # Redirect to the presigned URL
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url)
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f"Video not found: {str(e)}")

@app.get("/videos/{video_id}/stream")
async def stream_video(video_id: str, request: Request):
    """Stream a specific video by ID with range request support"""
    # Get the video
    async with db_pool.acquire() as conn:
        video = await conn.fetchrow(
            "SELECT video_path FROM videos WHERE id = $1",
            uuid.UUID(video_id)
        )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = video["video_path"]
    minio_client = get_minio_client()

    return await stream_video_with_range(request, video_path, minio_client)

@app.post("/clips", response_model=Clip)
async def create_clip(clip: ClipCreate, background_tasks: BackgroundTasks):
    """Create a new clip from a game video"""
    # Verify video exists
    async with db_pool.acquire() as conn:
        video = await conn.fetchrow(
            "SELECT video_path FROM videos WHERE id = $1",
            uuid.UUID(clip.video_id)
        )

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Create clip record
    clip_id = str(uuid.uuid4())
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO clips (id, game_id, video_id, start_time, end_time, tags, notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, game_id, video_id, start_time, end_time, tags, notes, clip_path, status, created_at
            """,
            uuid.UUID(clip_id),
            uuid.UUID(clip.game_id),
            uuid.UUID(clip.video_id),
            clip.start_time,
            clip.end_time,
            clip.tags,
            clip.notes
        )

    # Queue clip processing
    background_tasks.add_task(
        process_clip,
        clip_id,
        video["video_path"],
        clip.start_time,
        clip.end_time
    )

    return {
        "id": str(row["id"]),
        "game_id": str(row["game_id"]),
        "video_id": str(row["video_id"]),
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "tags": row["tags"],
        "notes": row["notes"],
        "clip_path": row["clip_path"],
        "status": row["status"],
        "created_at": row["created_at"]
    }

@app.get("/clips", response_model=List[Clip])
async def list_clips(game_id: Optional[str] = None, tag: Optional[str] = None):
    """List clips with optional filters"""
    query = "SELECT * FROM clips WHERE 1=1"
    params = []

    if game_id:
        params.append(uuid.UUID(game_id))
        query += f" AND game_id = ${len(params)}"

    if tag:
        params.append([tag])
        query += f" AND tags && ${len(params)}"

    query += " ORDER BY created_at DESC"

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [
        {
            "id": str(row["id"]),
            "game_id": str(row["game_id"]),
            "video_id": str(row["video_id"]),
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "tags": row["tags"],
            "notes": row["notes"],
            "clip_path": row["clip_path"],
            "status": row["status"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]

@app.get("/clips/{clip_id}", response_model=Clip)
async def get_clip(clip_id: str):
    """Get a specific clip"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM clips WHERE id = $1",
            uuid.UUID(clip_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Clip not found")

    return {
        "id": str(row["id"]),
        "game_id": str(row["game_id"]),
        "video_id": str(row["video_id"]),
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "tags": row["tags"],
        "notes": row["notes"],
        "clip_path": row["clip_path"],
        "status": row["status"],
        "created_at": row["created_at"]
    }

@app.put("/clips/{clip_id}", response_model=Clip)
async def update_clip(clip_id: str, clip: ClipCreate):
    """Update clip metadata (tags, notes, timestamps)"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE clips
            SET start_time = $1, end_time = $2, tags = $3, notes = $4
            WHERE id = $5
            RETURNING id, game_id, video_id, start_time, end_time, tags, notes, clip_path, status, created_at
            """,
            clip.start_time, clip.end_time, clip.tags, clip.notes, uuid.UUID(clip_id)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Clip not found")

    return {
        "id": str(row["id"]),
        "game_id": str(row["game_id"]),
        "video_id": str(row["video_id"]),
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "tags": row["tags"],
        "notes": row["notes"],
        "clip_path": row["clip_path"],
        "status": row["status"],
        "created_at": row["created_at"]
    }

@app.get("/clips/{clip_id}/stream")
async def stream_clip(clip_id: str, request: Request):
    """Stream a processed clip for viewing with range request support"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT clip_path, status FROM clips WHERE id = $1",
            uuid.UUID(clip_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Clip not found")

    if row["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Clip is not ready. Status: {row['status']}")

    # Stream from MinIO with range support
    minio_client = get_minio_client()
    return await stream_video_with_range(request, row["clip_path"], minio_client)

@app.get("/clips/{clip_id}/download")
async def download_clip(clip_id: str):
    """Download a processed clip"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT clip_path, status FROM clips WHERE id = $1",
            uuid.UUID(clip_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Clip not found")

    if row["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Clip is not ready. Status: {row['status']}")

    # Download from MinIO and stream
    minio_client = get_minio_client()
    try:
        response = minio_client.get_object(BUCKET_NAME, row["clip_path"])
        return StreamingResponse(
            response.stream(),
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename=clip_{clip_id}.mp4"}
        )
    except S3Error as e:
        raise HTTPException(status_code=404, detail="Clip file not found")

@app.delete("/clips/{clip_id}")
async def delete_clip(clip_id: str):
    """Delete a clip"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT clip_path FROM clips WHERE id = $1",
            uuid.UUID(clip_id)
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        # Delete from MinIO if exists
        if row["clip_path"]:
            minio_client = get_minio_client()
            try:
                minio_client.remove_object(BUCKET_NAME, row["clip_path"])
            except S3Error:
                pass
        
        # Delete from database
        await conn.execute(
            "DELETE FROM clips WHERE id = $1",
            uuid.UUID(clip_id)
        )
    
    return {"message": "Clip deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
