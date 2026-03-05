-- ============================================================================
-- MIGRATION 006: TARGET_STATS SCHEMA UPDATE
-- ============================================================================
-- Purpose: Add missing columns and update constraints for target_stats table
-- Issue: Code expects end_date and customer_search_term columns that don't exist
-- Safety: ADDITIVE changes + constraint update with data preservation
-- ============================================================================

-- Step 1: Add missing columns
-- ----------------------------------------------------------------------------

-- Add end_date column (tracks the last date in the aggregated week)
ALTER TABLE target_stats
ADD COLUMN IF NOT EXISTS end_date DATE;

-- Add customer_search_term column (actual search query, distinct from target_text)
ALTER TABLE target_stats
ADD COLUMN IF NOT EXISTS customer_search_term TEXT;

-- Step 2: Backfill end_date for existing rows
-- ----------------------------------------------------------------------------
-- Set end_date = start_date + 6 days (end of week) for existing data
UPDATE target_stats
SET end_date = start_date + INTERVAL '6 days'
WHERE end_date IS NULL;

-- Backfill customer_search_term from target_text where NULL
UPDATE target_stats
SET customer_search_term = target_text
WHERE customer_search_term IS NULL;

-- Step 3: Update unique constraint
-- ----------------------------------------------------------------------------
-- Drop old constraint (may fail if name differs, that's OK)
ALTER TABLE target_stats
DROP CONSTRAINT IF EXISTS target_stats_client_id_start_date_campaign_name_ad_group_na_key;

-- Drop any other possible constraint names
ALTER TABLE target_stats
DROP CONSTRAINT IF EXISTS target_stats_unique_key;

ALTER TABLE target_stats
DROP CONSTRAINT IF EXISTS unique_target_stats;

-- Create new unique constraint matching code expectations
-- Note: Two different INSERT paths use slightly different constraints:
-- 1. save_target_stats_batch: (client_id, start_date, campaign_name, ad_group_name, target_text, customer_search_term, match_type)
-- 2. reaggregate_target_stats: (client_id, start_date, campaign_name, ad_group_name, target_text, customer_search_term)
-- We use the more specific one (with match_type) as the table constraint

ALTER TABLE target_stats
ADD CONSTRAINT target_stats_unique_composite
UNIQUE (client_id, start_date, campaign_name, ad_group_name, target_text, customer_search_term, match_type);

-- Step 4: Create index for common queries involving new columns
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_target_stats_date_range
ON target_stats(client_id, start_date, end_date);

CREATE INDEX IF NOT EXISTS idx_target_stats_cst
ON target_stats(client_id, customer_search_term);

-- ============================================================================
-- VERIFICATION QUERY (run manually to confirm migration)
-- ============================================================================
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'target_stats'
-- ORDER BY ordinal_position;
-- ============================================================================
