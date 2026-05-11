-- nba lineup-simulator initial schema (v1)
-- Target: Postgres 16 + pgvector
-- Apply with: psql -1 -f migrations/0001_init.sql
-- Companion doc: docs/schema.md

BEGIN;

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- digest() / lineup_hash SQL helper

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

DO $$ BEGIN
    CREATE TYPE subject_type AS ENUM ('player', 'team', 'lineup', 'coach');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE season_type AS ENUM ('regular', 'preseason', 'playoffs', 'play_in');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- players
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS players (
    player_id     BIGINT PRIMARY KEY,
    full_name     TEXT NOT NULL,
    first_name    TEXT,
    last_name     TEXT,
    birth_date    DATE,
    height_inches INT,
    weight_lbs    INT,
    position      TEXT,
    handedness    TEXT,
    espn_slug     TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- teams
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS teams (
    team_id       INT PRIMARY KEY,
    abbreviation  TEXT NOT NULL UNIQUE,
    full_name     TEXT NOT NULL,
    conference    TEXT,
    division      TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- games
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS games (
    game_id       BIGINT PRIMARY KEY,
    season        INT NOT NULL,
    season_type   season_type NOT NULL,
    game_date     DATE NOT NULL,
    tipoff_at     TIMESTAMPTZ,
    home_team_id  INT NOT NULL REFERENCES teams(team_id),
    away_team_id  INT NOT NULL REFERENCES teams(team_id),
    home_score    INT,
    away_score    INT,
    venue         TEXT,
    attendance    INT,
    status        TEXT NOT NULL DEFAULT 'final',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (home_team_id <> away_team_id)
);

CREATE INDEX IF NOT EXISTS games_season_date_idx ON games (season, game_date);
CREATE INDEX IF NOT EXISTS games_home_season_idx ON games (home_team_id, season);
CREATE INDEX IF NOT EXISTS games_away_season_idx ON games (away_team_id, season);

-- ---------------------------------------------------------------------------
-- coaches
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS coaches (
    coach_id    BIGINT PRIMARY KEY,
    full_name   TEXT NOT NULL,
    first_name  TEXT,
    last_name   TEXT,
    birth_date  DATE,
    espn_slug   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- coach_games
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS coach_games (
    coach_id    BIGINT NOT NULL REFERENCES coaches(coach_id),
    game_id     BIGINT NOT NULL REFERENCES games(game_id),
    team_id     INT NOT NULL REFERENCES teams(team_id),
    role        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, team_id, role)
);

CREATE INDEX IF NOT EXISTS coach_games_coach_team_idx ON coach_games (coach_id, team_id);

-- ---------------------------------------------------------------------------
-- rosters
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rosters (
    season         INT NOT NULL,
    team_id        INT NOT NULL REFERENCES teams(team_id),
    player_id      BIGINT NOT NULL REFERENCES players(player_id),
    jersey         TEXT,
    start_date     DATE NOT NULL,
    end_date       DATE,
    acquired_via   TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (season, team_id, player_id, start_date),
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS rosters_player_season_idx ON rosters (player_id, season);

-- ---------------------------------------------------------------------------
-- pbp_events
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pbp_events (
    game_id            BIGINT NOT NULL REFERENCES games(game_id),
    sequence_no        INT NOT NULL,
    quarter            INT NOT NULL,
    clock_seconds      INT NOT NULL,
    wall_clock_at      TIMESTAMPTZ,
    team_id            INT REFERENCES teams(team_id),
    player_id          BIGINT REFERENCES players(player_id),
    assist_player_id   BIGINT REFERENCES players(player_id),
    event_type         TEXT NOT NULL,
    points_scored      SMALLINT NOT NULL DEFAULT 0,
    home_score         SMALLINT NOT NULL,
    away_score         SMALLINT NOT NULL,
    description        TEXT,
    players_on_floor   JSONB NOT NULL,
    raw                JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, sequence_no),
    CHECK (quarter >= 1),
    CHECK (clock_seconds >= 0),
    CHECK (points_scored BETWEEN 0 AND 3)
);

CREATE INDEX IF NOT EXISTS pbp_events_timeline_idx
    ON pbp_events (game_id, quarter, clock_seconds);

-- ---------------------------------------------------------------------------
-- lineup_stints
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS lineup_stints (
    stint_id              BIGSERIAL PRIMARY KEY,
    game_id               BIGINT NOT NULL REFERENCES games(game_id),
    season                INT NOT NULL,
    quarter               INT NOT NULL,
    start_clock_seconds   INT NOT NULL,
    end_clock_seconds     INT NOT NULL,
    duration_seconds      SMALLINT NOT NULL,
    home_team_id          INT NOT NULL REFERENCES teams(team_id),
    away_team_id          INT NOT NULL REFERENCES teams(team_id),
    home_lineup           INTEGER[] NOT NULL,
    away_lineup           INTEGER[] NOT NULL,
    home_lineup_hash      TEXT NOT NULL,
    away_lineup_hash      TEXT NOT NULL,
    home_pts              SMALLINT NOT NULL DEFAULT 0,
    away_pts              SMALLINT NOT NULL DEFAULT 0,
    pts                   SMALLINT NOT NULL DEFAULT 0,
    possessions           SMALLINT NOT NULL DEFAULT 0,
    possessions_home      SMALLINT NOT NULL DEFAULT 0,
    possessions_away      SMALLINT NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (quarter >= 1),
    CHECK (start_clock_seconds >= end_clock_seconds),
    CHECK (end_clock_seconds >= 0),
    CHECK (duration_seconds >= 0),
    CHECK (array_length(home_lineup, 1) = 5),
    CHECK (array_length(away_lineup, 1) = 5),
    CHECK (home_lineup_hash ~ '^[0-9a-f]{64}$'),
    CHECK (away_lineup_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS lineup_stints_timeline_idx
    ON lineup_stints (game_id, quarter, start_clock_seconds);
CREATE INDEX IF NOT EXISTS lineup_stints_home_hash_season_idx
    ON lineup_stints (home_lineup_hash, season);
CREATE INDEX IF NOT EXISTS lineup_stints_away_hash_season_idx
    ON lineup_stints (away_lineup_hash, season);
CREATE INDEX IF NOT EXISTS lineup_stints_season_idx
    ON lineup_stints (season);

-- ---------------------------------------------------------------------------
-- facts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS facts (
    fact_id       BIGSERIAL PRIMARY KEY,
    subject_type  subject_type NOT NULL,
    subject_id    TEXT NOT NULL,
    fact_key      TEXT NOT NULL,
    fact_value    JSONB NOT NULL,
    source        TEXT NOT NULL,
    season        INT,
    valid_from    DATE,
    valid_to      DATE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE INDEX IF NOT EXISTS facts_lookup_idx
    ON facts (subject_type, subject_id, fact_key);

-- Partial unique constraint: no duplicate (subject, key, season) — using a
-- sentinel -1 for NULL season because Postgres treats NULL as distinct in
-- btree uniqueness, which would let duplicate season-agnostic rows through.
CREATE UNIQUE INDEX IF NOT EXISTS facts_unique_per_season_idx
    ON facts (subject_type, subject_id, fact_key, COALESCE(season, -1));

-- ---------------------------------------------------------------------------
-- sim_cache
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sim_cache (
    cache_id        BIGSERIAL PRIMARY KEY,
    lineup1_hash    TEXT NOT NULL,
    lineup2_hash    TEXT NOT NULL,
    context_hash    TEXT NOT NULL,
    model_versions  JSONB NOT NULL,
    result          JSONB NOT NULL,
    hit_count       BIGINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_hit_at     TIMESTAMPTZ,
    CHECK (lineup1_hash ~ '^[0-9a-f]{64}$'),
    CHECK (lineup2_hash ~ '^[0-9a-f]{64}$'),
    CHECK (context_hash ~ '^[0-9a-f]{64}$')
);

CREATE UNIQUE INDEX IF NOT EXISTS sim_cache_key_idx
    ON sim_cache (lineup1_hash, lineup2_hash, context_hash);

-- ---------------------------------------------------------------------------
-- embeddings_player  (pgvector; placeholder dim = 128)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS embeddings_player (
    player_id       BIGINT NOT NULL REFERENCES players(player_id),
    season          INT NOT NULL,
    model_version   TEXT NOT NULL,
    embedding       vector(128) NOT NULL,
    minutes_sample  INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, season, model_version)
);

CREATE INDEX IF NOT EXISTS embeddings_player_ivfflat_idx
    ON embeddings_player
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS embeddings_player_model_idx
    ON embeddings_player (model_version);

COMMIT;
