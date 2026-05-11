-- 0002_pbp_status: flag games with unusable / sparse PBP data
-- Companion: docs/schema.md § "Migration 0002 — pbp_status"
-- Apply with: psql -1 -f migrations/0002_pbp_status.sql

BEGIN;

ALTER TABLE games
    ADD COLUMN IF NOT EXISTS pbp_status TEXT NOT NULL DEFAULT 'ok'
        CHECK (pbp_status IN ('ok', 'thin'));

-- Partial index: the vast majority of games are 'ok'; the queries we care
-- about are "show me the thin ones" (ingest-quality dashboards, skip lists
-- for stint derivation) which scan a tiny minority of rows.
CREATE INDEX IF NOT EXISTS games_pbp_status_thin_idx
    ON games (pbp_status)
    WHERE pbp_status <> 'ok';

COMMIT;
