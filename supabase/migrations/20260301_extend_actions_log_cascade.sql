-- Phase 4: Extend actions_log with PPC cascade context columns
-- Preserves what the cascade knew at decision time for future ML training.

ALTER TABLE actions_log
    ADD COLUMN IF NOT EXISTS ppc_diagnostic          TEXT,
    ADD COLUMN IF NOT EXISTS ppc_quadrant             TEXT,
    ADD COLUMN IF NOT EXISTS campaign_efficiency      TEXT,
    ADD COLUMN IF NOT EXISTS account_health_signal    TEXT,
    ADD COLUMN IF NOT EXISTS cascade_flags            TEXT[],
    ADD COLUMN IF NOT EXISTS campaign_recommendation  TEXT;
