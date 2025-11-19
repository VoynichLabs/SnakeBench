-- Migration: Add live game support
-- This adds status and current_state columns to the games table

-- Add status column to games table
ALTER TABLE games
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'completed'
CHECK(status IN ('queued', 'in_progress', 'completed', 'failed'));

-- Add current_state column to store live game state JSON
ALTER TABLE games
ADD COLUMN IF NOT EXISTS current_state TEXT;

-- Make replay_path nullable (it won't exist for in-progress games)
ALTER TABLE games
ALTER COLUMN replay_path DROP NOT NULL;

-- Create index on status for faster live game queries
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);

-- Update existing games to have 'completed' status
UPDATE games
SET status = 'completed'
WHERE status IS NULL;
