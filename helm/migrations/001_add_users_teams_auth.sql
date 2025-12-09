-- Migration 001: Add users, teams, and authentication tables
-- This migration is idempotent and can be run multiple times safely

-- Users table (unified for coaches, players, and parents)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    username TEXT UNIQUE,
    password_hash TEXT,
    auth_provider TEXT DEFAULT 'local',       -- 'google', 'local'
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('coach', 'player', 'parent')),
    phone TEXT,
    status TEXT DEFAULT 'invited',            -- 'invited', 'active', 'suspended'
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,
    CONSTRAINT email_or_username CHECK (email IS NOT NULL OR username IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Player profiles (optional extra info)
CREATE TABLE IF NOT EXISTS player_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    jersey_number TEXT,
    position TEXT,                            -- 'PG', 'SG', 'SF', 'PF', 'C'
    graduation_year INTEGER
);

-- Parent-player links
CREATE TABLE IF NOT EXISTS parent_links (
    parent_id UUID REFERENCES users(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,
    verified_at TIMESTAMP,
    PRIMARY KEY (parent_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_parent_links_parent ON parent_links(parent_id);
CREATE INDEX IF NOT EXISTS idx_parent_links_player ON parent_links(player_id);

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    season TEXT,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Team-coach relationship (multiple coaches per team)
CREATE TABLE IF NOT EXISTS team_coaches (
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    coach_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'assistant',            -- 'head', 'assistant'
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (team_id, coach_id)
);

CREATE INDEX IF NOT EXISTS idx_team_coaches_coach ON team_coaches(coach_id);

-- Team-player relationship
CREATE TABLE IF NOT EXISTS team_players (
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (team_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_team_players_player ON team_players(player_id);

-- Invites
CREATE TABLE IF NOT EXISTS invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    target_role TEXT NOT NULL,                -- 'player', 'parent'
    target_name TEXT,                         -- Pre-filled name
    linked_player_id UUID REFERENCES users(id), -- For parent invites
    expires_at TIMESTAMP NOT NULL,
    claimed_by UUID REFERENCES users(id),
    claimed_at TIMESTAMP,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invites_code ON invites(code);
CREATE INDEX IF NOT EXISTS idx_invites_team ON invites(team_id);

-- Add team_id to games table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='games' AND column_name='team_id'
    ) THEN
        ALTER TABLE games ADD COLUMN team_id UUID REFERENCES teams(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_games_team ON games(team_id);

-- Clip assignments
CREATE TABLE IF NOT EXISTS clip_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES users(id),
    message TEXT,
    priority TEXT DEFAULT 'normal',           -- 'high', 'normal', 'low'
    viewed_at TIMESTAMP,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clip_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_clip_assignments_player ON clip_assignments(player_id);
CREATE INDEX IF NOT EXISTS idx_clip_assignments_clip ON clip_assignments(clip_id);

-- Clip annotations
CREATE TABLE IF NOT EXISTS clip_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clip_id UUID REFERENCES clips(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id),
    drawing_data JSONB,                       -- Fabric.js canvas state
    audio_path TEXT,                          -- MinIO path to audio file
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clip_annotations_clip ON clip_annotations(clip_id);

-- Player game stats
CREATE TABLE IF NOT EXISTS player_game_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID REFERENCES games(id) ON DELETE CASCADE,
    player_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Scoring
    points INTEGER DEFAULT 0,
    field_goals_made INTEGER DEFAULT 0,
    field_goals_attempted INTEGER DEFAULT 0,
    three_pointers_made INTEGER DEFAULT 0,
    three_pointers_attempted INTEGER DEFAULT 0,
    free_throws_made INTEGER DEFAULT 0,
    free_throws_attempted INTEGER DEFAULT 0,

    -- Rebounds
    offensive_rebounds INTEGER DEFAULT 0,
    defensive_rebounds INTEGER DEFAULT 0,

    -- Other
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
);

CREATE INDEX IF NOT EXISTS idx_player_game_stats_player ON player_game_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_player_game_stats_game ON player_game_stats(game_id);

-- Notification preferences (for future)
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    notify_new_clip BOOLEAN DEFAULT true,
    notify_new_message BOOLEAN DEFAULT true
);

-- Notifications (for future)
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
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(user_id) WHERE read_at IS NULL;

-- Refresh tokens (for JWT refresh functionality)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
