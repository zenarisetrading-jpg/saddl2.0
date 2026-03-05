DO $$
BEGIN
    IF current_schema() = 'saddl' THEN
        RAISE EXCEPTION 'Rollback called from wrong schema context. Aborting.';
    END IF;
END $$;

DROP SCHEMA IF EXISTS sc_analytics CASCADE;
DROP SCHEMA IF EXISTS sc_raw CASCADE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.schemata WHERE schema_name = 'saddl'
    ) THEN
        RAISE WARNING 'saddl schema not found - verify manually';
    ELSE
        RAISE NOTICE 'Confirmed: saddl schema untouched';
    END IF;
END $$;
