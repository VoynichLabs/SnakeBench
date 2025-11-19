-- Add metadata column to evaluation_queue for storing placement state
-- This supports the binary search placement system

ALTER TABLE evaluation_queue
ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Add index for faster metadata queries
CREATE INDEX IF NOT EXISTS idx_evaluation_queue_metadata
ON evaluation_queue USING gin (metadata);

-- Add comment
COMMENT ON COLUMN evaluation_queue.metadata IS 'JSON metadata for placement state tracking (binary search algorithm)';
