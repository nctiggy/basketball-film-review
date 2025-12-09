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
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Import auth routes
from backend.routes import (
    auth_router,
    player_router,
    parent_router,
    invites_router,
    teams_router,
    assignments_router,
    annotations_router,
    stats_router
)
from backend.auth import dependencies as auth_deps
from backend.auth import get_current_user
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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

    # Set db_pool for auth dependencies
    auth_deps.set_db_pool(db_pool)

    # Initialize Kubernetes client (in-cluster config)
    try:
        config.load_incluster_config()
        print("Loaded in-cluster Kubernetes config")
    except config.ConfigException:
        print("Warning: Could not load in-cluster config, Kubernetes features disabled")

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
                home_team_color VARCHAR(50) DEFAULT 'white',
                away_team_color VARCHAR(50) DEFAULT 'dark',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Add team color columns to existing games table if they don't exist
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='games' AND column_name='home_team_color'
                ) THEN
                    ALTER TABLE games ADD COLUMN home_team_color VARCHAR(50) DEFAULT 'white';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='games' AND column_name='away_team_color'
                ) THEN
                    ALTER TABLE games ADD COLUMN away_team_color VARCHAR(50) DEFAULT 'dark';
                END IF;
            END $$;
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
                players TEXT[] DEFAULT '{}',
                notes TEXT,
                clip_path VARCHAR(500),
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Add players column to existing clips table if it doesn't exist
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='clips' AND column_name='players'
                ) THEN
                    ALTER TABLE clips ADD COLUMN players TEXT[] DEFAULT '{}';
                END IF;
            END $$;
        """)

        # Create clip_analyses table for AI analysis results
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS clip_analyses (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                clip_id UUID REFERENCES clips(id) ON DELETE CASCADE UNIQUE,
                home_shots_attempted INTEGER DEFAULT 0,
                home_shots_made INTEGER DEFAULT 0,
                home_offensive_rebounds INTEGER DEFAULT 0,
                home_defensive_rebounds INTEGER DEFAULT 0,
                away_shots_attempted INTEGER DEFAULT 0,
                away_shots_made INTEGER DEFAULT 0,
                away_offensive_rebounds INTEGER DEFAULT 0,
                away_defensive_rebounds INTEGER DEFAULT 0,
                play_description TEXT,
                confidence VARCHAR(20),
                notes TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            )
        """)

        # Create auth and user management tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email TEXT UNIQUE,
                username TEXT UNIQUE,
                password_hash TEXT,
                auth_provider TEXT DEFAULT 'local',
                display_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('coach', 'player', 'parent')),
                phone TEXT,
                status TEXT DEFAULT 'invited',
                created_by UUID REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW(),
                last_login_at TIMESTAMP,
                CONSTRAINT email_or_username CHECK (email IS NOT NULL OR username IS NOT NULL)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS player_profiles (
                user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                jersey_number TEXT,
                position TEXT,
                graduation_year INTEGER
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS parent_links (
                parent_id UUID REFERENCES users(id) ON DELETE CASCADE,
                player_id UUID REFERENCES users(id) ON DELETE CASCADE,
                verified_at TIMESTAMP,
                PRIMARY KEY (parent_id, player_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                season TEXT,
                created_by UUID REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS team_coaches (
                team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
                coach_id UUID REFERENCES users(id) ON DELETE CASCADE,
                role TEXT DEFAULT 'assistant',
                added_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (team_id, coach_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS team_players (
                team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
                player_id UUID REFERENCES users(id) ON DELETE CASCADE,
                added_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (team_id, player_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                code TEXT UNIQUE NOT NULL,
                team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
                target_role TEXT NOT NULL,
                target_name TEXT,
                linked_player_id UUID REFERENCES users(id),
                expires_at TIMESTAMP NOT NULL,
                claimed_by UUID REFERENCES users(id),
                claimed_at TIMESTAMP,
                created_by UUID REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS clip_assignments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
                player_id UUID REFERENCES users(id) ON DELETE CASCADE,
                assigned_by UUID REFERENCES users(id),
                message TEXT,
                priority TEXT DEFAULT 'normal',
                viewed_at TIMESTAMP,
                acknowledged_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(clip_id, player_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS clip_annotations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
                created_by UUID REFERENCES users(id),
                drawing_data JSONB,
                audio_path TEXT,
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS player_game_stats (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                game_id UUID REFERENCES games(id) ON DELETE CASCADE,
                player_id UUID REFERENCES users(id) ON DELETE CASCADE,
                points INTEGER DEFAULT 0,
                field_goals_made INTEGER DEFAULT 0,
                field_goals_attempted INTEGER DEFAULT 0,
                three_pointers_made INTEGER DEFAULT 0,
                three_pointers_attempted INTEGER DEFAULT 0,
                free_throws_made INTEGER DEFAULT 0,
                free_throws_attempted INTEGER DEFAULT 0,
                offensive_rebounds INTEGER DEFAULT 0,
                defensive_rebounds INTEGER DEFAULT 0,
                assists INTEGER DEFAULT 0,
                steals INTEGER DEFAULT 0,
                blocks INTEGER DEFAULT 0,
                turnovers INTEGER DEFAULT 0,
                fouls INTEGER DEFAULT 0,
                minutes_played INTEGER,
                recorded_by UUID REFERENCES users(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(game_id, player_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                email_enabled BOOLEAN DEFAULT true,
                sms_enabled BOOLEAN DEFAULT false,
                notify_new_clip BOOLEAN DEFAULT true,
                notify_new_message BOOLEAN DEFAULT true
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                data JSONB,
                read_at TIMESTAMP,
                sent_email_at TIMESTAMP,
                sent_sms_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                revoked_at TIMESTAMP
            )
        """)

        # Add team_id to games table if it doesn't exist
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='games' AND column_name='team_id'
                ) THEN
                    ALTER TABLE games ADD COLUMN team_id UUID REFERENCES teams(id);
                END IF;
            END $$;
        """)

        # Create indexes for new tables
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_parent_links_parent ON parent_links(parent_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_parent_links_player ON parent_links(player_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_team_coaches_coach ON team_coaches(coach_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_team_players_player ON team_players(player_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_invites_code ON invites(code)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_invites_team ON invites(team_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_games_team ON games(team_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_assignments_player ON clip_assignments(player_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_assignments_clip ON clip_assignments(clip_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_annotations_clip ON clip_annotations(clip_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_player_game_stats_player ON player_game_stats(player_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_player_game_stats_game ON player_game_stats(game_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash)")
    
    yield
    
    # Shutdown
    await db_pool.close()

app = FastAPI(title="Basketball Film Review", lifespan=lifespan)

# Security middleware
from backend.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# CORS middleware (must be last to apply first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(player_router)
app.include_router(parent_router)
app.include_router(invites_router)
app.include_router(teams_router)
app.include_router(assignments_router)
app.include_router(annotations_router)
app.include_router(stats_router)

# Pydantic models
class GameCreate(BaseModel):
    name: str
    date: str
    home_team_color: Optional[str] = "white"
    away_team_color: Optional[str] = "dark"

class Game(BaseModel):
    id: str
    name: str
    date: date
    home_team_color: str
    away_team_color: str
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
    players: List[str] = []
    notes: Optional[str] = None

class Clip(BaseModel):
    id: str
    game_id: str
    video_id: str
    start_time: str
    end_time: str
    tags: List[str]
    players: List[str]
    notes: Optional[str]
    clip_path: Optional[str]
    status: str
    created_at: datetime

class ClipAnalysis(BaseModel):
    id: str
    clip_id: str
    home_shots_attempted: int
    home_shots_made: int
    home_offensive_rebounds: int
    home_defensive_rebounds: int
    away_shots_attempted: int
    away_shots_made: int
    away_offensive_rebounds: int
    away_defensive_rebounds: int
    play_description: Optional[str]
    confidence: Optional[str]
    notes: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

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

        # Async generator to yield chunks from MinIO stream
        async def stream_generator(response_data, chunk_size=1024*1024):  # 1MB chunks
            try:
                loop = asyncio.get_event_loop()
                while True:
                    # Read chunk in thread pool to avoid blocking
                    chunk = await loop.run_in_executor(None, response_data.read, chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                # Ensure stream is closed
                response_data.close()
                response_data.release_conn()

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
                stream_generator(response_data),
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
                stream_generator(response_data),
                media_type="video/mp4",
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(file_size),
                    "Content-Disposition": "inline"
                }
            )
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f"Video not found: {str(e)}")

async def create_clipjob(clip_id: str, game_id: str, video_id: str, game_video_path: str, start_time: str, end_time: str):
    """Create a ClipJob custom resource for the operator to process"""
    try:
        # Create Kubernetes API client
        custom_api = client.CustomObjectsApi()

        # Define the ClipJob resource
        clip_path = f"clips/{clip_id}.mp4"
        clipjob = {
            "apiVersion": "filmreview.io/v1alpha1",
            "kind": "ClipJob",
            "metadata": {
                "name": f"clip-{clip_id}",
                "namespace": "film-review"
            },
            "spec": {
                "clipId": clip_id,
                "gameId": game_id,
                "videoId": video_id,
                "videoPath": game_video_path,
                "clipPath": clip_path,
                "startTime": start_time,
                "endTime": end_time,
                "ttlSecondsAfterFinished": 3600,
                "backoffLimit": 3
            }
        }

        # Create the ClipJob resource
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: custom_api.create_namespaced_custom_object(
                group="filmreview.io",
                version="v1alpha1",
                namespace="film-review",
                plural="clipjobs",
                body=clipjob
            )
        )

        print(f"Created ClipJob for clip {clip_id}")

    except ApiException as e:
        print(f"Error creating ClipJob for clip {clip_id}: {e}")
        # Update clip status to failed
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE clips SET status = 'failed' WHERE id = $1",
                uuid.UUID(clip_id)
            )
    except Exception as e:
        print(f"Unexpected error creating ClipJob for clip {clip_id}: {str(e)}")
        # Update clip status to failed
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
    date: str = Form(...),
    home_team_color: str = Form("white"),
    away_team_color: str = Form("dark"),
    current_user: dict = Depends(get_current_user)
):
    """Create a new game - requires authentication"""
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
            INSERT INTO games (id, name, date, home_team_color, away_team_color)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, date, home_team_color, away_team_color, created_at
            """,
            uuid.UUID(game_id), name, game_date, home_team_color, away_team_color
        )

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "date": row["date"],
        "home_team_color": row["home_team_color"],
        "away_team_color": row["away_team_color"],
        "created_at": row["created_at"],
        "video_count": 0
    }

@app.post("/games/{game_id}/videos", response_model=Video)
async def upload_video(
    game_id: str,
    video: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a video for a game - requires authentication"""
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
async def list_game_videos(game_id: str, current_user: dict = Depends(get_current_user)):
    """List all videos for a game - requires authentication"""
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
async def get_video(video_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific video - requires authentication"""
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
    filename: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Update video metadata (filename only) - requires authentication"""
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
async def delete_video(video_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a video and all associated clips - requires authentication"""
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
async def list_games(current_user: dict = Depends(get_current_user)):
    """List all games - requires authentication"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT g.id, g.name, g.date, g.home_team_color, g.away_team_color, g.created_at, COUNT(v.id) as video_count
            FROM games g
            LEFT JOIN videos v ON g.id = v.game_id
            GROUP BY g.id, g.name, g.date, g.home_team_color, g.away_team_color, g.created_at
            ORDER BY g.date DESC
        """)

    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "date": row["date"],
            "home_team_color": row["home_team_color"] or "white",
            "away_team_color": row["away_team_color"] or "dark",
            "created_at": row["created_at"],
            "video_count": row["video_count"]
        }
        for row in rows
    ]

@app.get("/games/{game_id}", response_model=Game)
async def get_game(game_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific game - requires authentication"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT g.id, g.name, g.date, g.home_team_color, g.away_team_color, g.created_at, COUNT(v.id) as video_count
            FROM games g
            LEFT JOIN videos v ON g.id = v.game_id
            WHERE g.id = $1
            GROUP BY g.id, g.name, g.date, g.home_team_color, g.away_team_color, g.created_at
            """,
            uuid.UUID(game_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Game not found")

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "date": row["date"],
        "home_team_color": row["home_team_color"] or "white",
        "away_team_color": row["away_team_color"] or "dark",
        "created_at": row["created_at"],
        "video_count": row["video_count"]
    }

@app.put("/games/{game_id}", response_model=Game)
async def update_game(
    game_id: str,
    name: str = Form(...),
    date: str = Form(...),
    home_team_color: str = Form("white"),
    away_team_color: str = Form("dark"),
    current_user: dict = Depends(get_current_user)
):
    """Update a game - requires authentication"""
    try:
        game_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE games
            SET name = $1, date = $2, home_team_color = $3, away_team_color = $4
            WHERE id = $5
            RETURNING id, name, date, home_team_color, away_team_color, created_at
            """,
            name, game_date, home_team_color, away_team_color, uuid.UUID(game_id)
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
        "home_team_color": row["home_team_color"],
        "away_team_color": row["away_team_color"],
        "created_at": row["created_at"],
        "video_count": video_count
    }

@app.delete("/games/{game_id}")
async def delete_game(game_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a game and all associated videos and clips - requires authentication"""
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
async def stream_game_video(game_id: str, current_user: dict = Depends(get_current_user)):
    """Stream the first video for a game - requires authentication"""
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
async def create_clip(clip: ClipCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Create a new clip from a game video - requires authentication"""
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
            INSERT INTO clips (id, game_id, video_id, start_time, end_time, tags, players, notes)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, game_id, video_id, start_time, end_time, tags, players, notes, clip_path, status, created_at
            """,
            uuid.UUID(clip_id),
            uuid.UUID(clip.game_id),
            uuid.UUID(clip.video_id),
            clip.start_time,
            clip.end_time,
            clip.tags,
            clip.players,
            clip.notes
        )

    # Create ClipJob for async processing via operator
    background_tasks.add_task(
        create_clipjob,
        clip_id,
        clip.game_id,
        clip.video_id,
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
        "players": row["players"],
        "notes": row["notes"],
        "clip_path": row["clip_path"],
        "status": row["status"],
        "created_at": row["created_at"]
    }

@app.get("/clips", response_model=List[Clip])
async def list_clips(game_id: Optional[str] = None, tag: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """List clips with optional filters - requires authentication"""
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
        "players": row["players"],
            "notes": row["notes"],
            "clip_path": row["clip_path"],
            "status": row["status"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]

@app.get("/clips/{clip_id}", response_model=Clip)
async def get_clip(clip_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific clip - requires authentication"""
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
        "players": row["players"],
        "notes": row["notes"],
        "clip_path": row["clip_path"],
        "status": row["status"],
        "created_at": row["created_at"]
    }

@app.put("/clips/{clip_id}", response_model=Clip)
async def update_clip(clip_id: str, clip: ClipCreate, current_user: dict = Depends(get_current_user)):
    """Update clip metadata (tags, players, notes, timestamps) - requires authentication"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE clips
            SET start_time = $1, end_time = $2, tags = $3, players = $4, notes = $5
            WHERE id = $6
            RETURNING id, game_id, video_id, start_time, end_time, tags, players, notes, clip_path, status, created_at
            """,
            clip.start_time, clip.end_time, clip.tags, clip.players, clip.notes, uuid.UUID(clip_id)
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
        "players": row["players"],
        "notes": row["notes"],
        "clip_path": row["clip_path"],
        "status": row["status"],
        "created_at": row["created_at"]
    }

@app.get("/clips/{clip_id}/stream")
async def stream_clip(clip_id: str, request: Request, current_user: Optional[dict] = Depends(auth_deps.get_current_user_optional)):
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

    # Authorization check: players can only stream clips assigned to them
    if current_user and current_user["role"] == "player":
        async with db_pool.acquire() as conn:
            is_assigned = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM clip_assignments
                    WHERE clip_id = $1 AND player_id = $2
                )
                """,
                uuid.UUID(clip_id),
                uuid.UUID(current_user["id"])
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this clip"
                )

    # Parents can stream clips assigned to their children
    if current_user and current_user["role"] == "parent":
        async with db_pool.acquire() as conn:
            has_access = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM clip_assignments ca
                    INNER JOIN parent_links pl ON ca.player_id = pl.player_id
                    WHERE ca.clip_id = $1 AND pl.parent_id = $2
                )
                """,
                uuid.UUID(clip_id),
                uuid.UUID(current_user["id"])
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this clip"
                )

    # Stream from MinIO with range support
    minio_client = get_minio_client()
    return await stream_video_with_range(request, row["clip_path"], minio_client)

@app.get("/clips/{clip_id}/download")
async def download_clip(clip_id: str, current_user: dict = Depends(get_current_user)):
    """Download a processed clip - requires authentication"""
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
async def delete_clip(clip_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a clip - requires authentication"""
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

@app.get("/players")
async def get_players(current_user: dict = Depends(get_current_user)):
    """Get all unique players from clips - requires authentication"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT unnest(players) as player FROM clips WHERE array_length(players, 1) > 0 ORDER BY player"
        )

    return [row["player"] for row in rows]


# Analysis endpoints
async def create_analysisjob(clip_id: str, game_id: str, clip_path: str, home_team_color: str, away_team_color: str):
    """Create an AnalysisJob custom resource for the operator to process"""
    try:
        # Create Kubernetes API client
        custom_api = client.CustomObjectsApi()

        # Define the AnalysisJob resource
        analysisjob = {
            "apiVersion": "filmreview.io/v1alpha1",
            "kind": "AnalysisJob",
            "metadata": {
                "name": f"analysis-{clip_id[:8]}",
                "namespace": "film-review"
            },
            "spec": {
                "clipId": clip_id,
                "gameId": game_id,
                "clipPath": clip_path,
                "homeTeamColor": home_team_color,
                "awayTeamColor": away_team_color,
                "provider": "qwen",  # Use Qwen2-VL via Replicate for native video understanding
                "framesPerSecond": 4.0,
                "ttlSecondsAfterFinished": 3600,
                "backoffLimit": 2
            }
        }

        # Create the AnalysisJob resource
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: custom_api.create_namespaced_custom_object(
                group="filmreview.io",
                version="v1alpha1",
                namespace="film-review",
                plural="analysisjobs",
                body=analysisjob
            )
        )

        print(f"Created AnalysisJob for clip {clip_id}")

    except ApiException as e:
        print(f"Error creating AnalysisJob for clip {clip_id}: {e}")
        # Update analysis status to failed
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE clip_analyses SET status = 'failed', error_message = $1 WHERE clip_id = $2",
                str(e), uuid.UUID(clip_id)
            )
    except Exception as e:
        print(f"Unexpected error creating AnalysisJob for clip {clip_id}: {str(e)}")
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE clip_analyses SET status = 'failed', error_message = $1 WHERE clip_id = $2",
                str(e), uuid.UUID(clip_id)
            )


@app.post("/clips/{clip_id}/analyze", response_model=ClipAnalysis)
async def analyze_clip(clip_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Start AI analysis of a clip - requires authentication"""
    # Verify clip exists and is completed
    async with db_pool.acquire() as conn:
        clip = await conn.fetchrow(
            "SELECT c.id, c.game_id, c.clip_path, c.status, g.home_team_color, g.away_team_color FROM clips c JOIN games g ON c.game_id = g.id WHERE c.id = $1",
            uuid.UUID(clip_id)
        )

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if clip["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Clip is not ready for analysis. Status: {clip['status']}")

    # Check if analysis already exists
    async with db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM clip_analyses WHERE clip_id = $1",
            uuid.UUID(clip_id)
        )

        if existing:
            # If already completed or in progress, return it
            if existing["status"] in ["completed", "processing"]:
                return {
                    "id": str(existing["id"]),
                    "clip_id": str(existing["clip_id"]),
                    "home_shots_attempted": existing["home_shots_attempted"],
                    "home_shots_made": existing["home_shots_made"],
                    "home_offensive_rebounds": existing["home_offensive_rebounds"],
                    "home_defensive_rebounds": existing["home_defensive_rebounds"],
                    "away_shots_attempted": existing["away_shots_attempted"],
                    "away_shots_made": existing["away_shots_made"],
                    "away_offensive_rebounds": existing["away_offensive_rebounds"],
                    "away_defensive_rebounds": existing["away_defensive_rebounds"],
                    "play_description": existing["play_description"],
                    "confidence": existing["confidence"],
                    "notes": existing["notes"],
                    "status": existing["status"],
                    "error_message": existing["error_message"],
                    "created_at": existing["created_at"],
                    "completed_at": existing["completed_at"]
                }
            # If failed or pending, delete and recreate
            await conn.execute("DELETE FROM clip_analyses WHERE clip_id = $1", uuid.UUID(clip_id))

        # Create new analysis record
        row = await conn.fetchrow(
            """
            INSERT INTO clip_analyses (clip_id, status)
            VALUES ($1, 'pending')
            RETURNING *
            """,
            uuid.UUID(clip_id)
        )

    # Create AnalysisJob for async processing via operator
    background_tasks.add_task(
        create_analysisjob,
        clip_id,
        str(clip["game_id"]),
        clip["clip_path"],
        clip["home_team_color"] or "white",
        clip["away_team_color"] or "dark"
    )

    return {
        "id": str(row["id"]),
        "clip_id": str(row["clip_id"]),
        "home_shots_attempted": row["home_shots_attempted"],
        "home_shots_made": row["home_shots_made"],
        "home_offensive_rebounds": row["home_offensive_rebounds"],
        "home_defensive_rebounds": row["home_defensive_rebounds"],
        "away_shots_attempted": row["away_shots_attempted"],
        "away_shots_made": row["away_shots_made"],
        "away_offensive_rebounds": row["away_offensive_rebounds"],
        "away_defensive_rebounds": row["away_defensive_rebounds"],
        "play_description": row["play_description"],
        "confidence": row["confidence"],
        "notes": row["notes"],
        "status": row["status"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"]
    }


@app.get("/clips/{clip_id}/analysis", response_model=ClipAnalysis)
async def get_clip_analysis(clip_id: str, current_user: dict = Depends(get_current_user)):
    """Get the analysis results for a clip - requires authentication"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM clip_analyses WHERE clip_id = $1",
            uuid.UUID(clip_id)
        )

    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found for this clip")

    return {
        "id": str(row["id"]),
        "clip_id": str(row["clip_id"]),
        "home_shots_attempted": row["home_shots_attempted"],
        "home_shots_made": row["home_shots_made"],
        "home_offensive_rebounds": row["home_offensive_rebounds"],
        "home_defensive_rebounds": row["home_defensive_rebounds"],
        "away_shots_attempted": row["away_shots_attempted"],
        "away_shots_made": row["away_shots_made"],
        "away_offensive_rebounds": row["away_offensive_rebounds"],
        "away_defensive_rebounds": row["away_defensive_rebounds"],
        "play_description": row["play_description"],
        "confidence": row["confidence"],
        "notes": row["notes"],
        "status": row["status"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"]
    }


@app.delete("/clips/{clip_id}/analysis")
async def delete_clip_analysis(clip_id: str, current_user: dict = Depends(get_current_user)):
    """Delete analysis for a clip - requires authentication"""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM clip_analyses WHERE clip_id = $1",
            uuid.UUID(clip_id)
        )

        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Analysis not found for this clip")

    return {"message": "Analysis deleted successfully"}


# Annotations endpoints
@app.get("/clips/{clip_id}/annotations")
async def get_clip_annotations(clip_id: str, current_user: Optional[dict] = Depends(auth_deps.get_current_user_optional)):
    """
    Get annotations for a clip (drawings and audio overlay).

    Authorization:
    - Coaches: can view any clip
    - Players: can only view clips assigned to them
    - Parents: can view clips assigned to their children
    """
    # Verify clip exists
    async with db_pool.acquire() as conn:
        clip = await conn.fetchrow(
            "SELECT id FROM clips WHERE id = $1",
            uuid.UUID(clip_id)
        )

        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")

        # Authorization check for players
        if current_user and current_user["role"] == "player":
            is_assigned = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM clip_assignments
                    WHERE clip_id = $1 AND player_id = $2
                )
                """,
                uuid.UUID(clip_id),
                uuid.UUID(current_user["id"])
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this clip"
                )

        # Authorization check for parents
        if current_user and current_user["role"] == "parent":
            has_access = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM clip_assignments ca
                    INNER JOIN parent_links pl ON ca.player_id = pl.player_id
                    WHERE ca.clip_id = $1 AND pl.parent_id = $2
                )
                """,
                uuid.UUID(clip_id),
                uuid.UUID(current_user["id"])
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this clip"
                )

        # Get the latest annotation for this clip
        annotation = await conn.fetchrow(
            """
            SELECT id, clip_id, created_by, drawing_data, audio_path, version, created_at, updated_at
            FROM clip_annotations
            WHERE clip_id = $1
            ORDER BY version DESC
            LIMIT 1
            """,
            uuid.UUID(clip_id)
        )

        if not annotation:
            # Return empty annotation if none exists
            return {
                "clip_id": clip_id,
                "drawing_data": None,
                "audio_path": None,
                "version": 0
            }

        return {
            "id": str(annotation["id"]),
            "clip_id": str(annotation["clip_id"]),
            "created_by": str(annotation["created_by"]) if annotation["created_by"] else None,
            "drawing_data": annotation["drawing_data"],
            "audio_path": annotation["audio_path"],
            "version": annotation["version"],
            "created_at": annotation["created_at"],
            "updated_at": annotation["updated_at"]
        }


@app.get("/clips/{clip_id}/audio")
async def get_clip_audio(clip_id: str, current_user: Optional[dict] = Depends(auth_deps.get_current_user_optional)):
    """
    Get audio overlay for a clip.

    Streams the audio file from MinIO with authorization checks.
    """
    async with db_pool.acquire() as conn:
        # Get annotation with audio path
        annotation = await conn.fetchrow(
            """
            SELECT audio_path
            FROM clip_annotations
            WHERE clip_id = $1 AND audio_path IS NOT NULL
            ORDER BY version DESC
            LIMIT 1
            """,
            uuid.UUID(clip_id)
        )

        if not annotation or not annotation["audio_path"]:
            raise HTTPException(status_code=404, detail="No audio overlay found for this clip")

        # Authorization check for players
        if current_user and current_user["role"] == "player":
            is_assigned = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM clip_assignments
                    WHERE clip_id = $1 AND player_id = $2
                )
                """,
                uuid.UUID(clip_id),
                uuid.UUID(current_user["id"])
            )
            if not is_assigned:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this clip"
                )

        # Authorization check for parents
        if current_user and current_user["role"] == "parent":
            has_access = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM clip_assignments ca
                    INNER JOIN parent_links pl ON ca.player_id = pl.player_id
                    WHERE ca.clip_id = $1 AND pl.parent_id = $2
                )
                """,
                uuid.UUID(clip_id),
                uuid.UUID(current_user["id"])
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this clip"
                )

        # Stream audio from MinIO
        minio_client = get_minio_client()
        try:
            response = minio_client.get_object(BUCKET_NAME, annotation["audio_path"])
            return StreamingResponse(
                response.stream(),
                media_type="audio/mpeg",
                headers={"Content-Disposition": f"inline; filename=audio_{clip_id}.mp3"}
            )
        except S3Error as e:
            raise HTTPException(status_code=404, detail="Audio file not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
