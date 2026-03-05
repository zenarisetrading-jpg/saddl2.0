-- Migration: add marketplace_id and region_endpoint to client_settings
-- These columns store the Amazon marketplace each client authorized during OAuth.
-- Nullable intentionally — existing rows will be backfilled via fallback logic
-- in the worker until all clients have gone through the updated OAuth flow.

ALTER TABLE client_settings
ADD COLUMN IF NOT EXISTS marketplace_id TEXT,
ADD COLUMN IF NOT EXISTS region_endpoint TEXT;

COMMENT ON COLUMN client_settings.marketplace_id IS 'Amazon marketplace ID discovered during OAuth (e.g. A2VIGQ35RCS4UG for UAE, A17E79C6D8DWNP for KSA)';
COMMENT ON COLUMN client_settings.region_endpoint IS 'SP-API regional endpoint for this marketplace (e.g. sellingpartnerapi-eu.amazon.com)';
