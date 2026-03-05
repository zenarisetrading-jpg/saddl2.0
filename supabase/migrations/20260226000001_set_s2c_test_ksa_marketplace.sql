-- One-time fix: set s2c_test (Aslam's KSA account) to the correct marketplace.
-- This account was onboarded before marketplace discovery was added to the OAuth flow,
-- so it has no marketplace_id / region_endpoint stored. Without this fix the worker
-- would fall back to UAE (A2VIGQ35RCS4UG) and return 0 rows from the wrong marketplace.

UPDATE client_settings
SET
    marketplace_id   = 'A17E79C6D8DWNP',
    region_endpoint  = 'sellingpartnerapi-eu.amazon.com',
    onboarding_status = 'connected'
WHERE client_id = 's2c_test';

-- Verify
-- SELECT client_id, marketplace_id, region_endpoint, onboarding_status
-- FROM client_settings
-- WHERE client_id = 's2c_test';
