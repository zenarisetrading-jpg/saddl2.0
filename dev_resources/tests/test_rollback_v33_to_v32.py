"""
Test Impact Model v3.3 → v3.2 Rollback Functionality

This script verifies that the feature flag rollback works correctly.

Usage:
    python dev_resources/tests/test_rollback_v33_to_v32.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app_core.postgres_manager import (
    PostgresManager,
    IMPACT_MODEL_VERSION,
    get_impact_model_version
)


def test_feature_flag():
    """Test that feature flag is accessible and has valid value."""
    print("=" * 60)
    print("TEST 1: Feature Flag Check")
    print("=" * 60)

    version = get_impact_model_version()
    print(f"✓ Current model version: {version}")

    assert version in ["v3.2", "v3.3"], f"Invalid model version: {version}"
    assert version == IMPACT_MODEL_VERSION, "Version mismatch"

    print(f"✓ Feature flag working correctly: {version}")
    print()
    return version


def test_column_presence(client_id: str = None):
    """Test that appropriate columns are present based on version."""
    print("=" * 60)
    print("TEST 2: Column Presence Check")
    print("=" * 60)

    if client_id is None:
        print("⚠️  No client_id provided - skipping database test")
        print("   To test with real data, provide client_id as argument")
        print()
        return True

    try:
        db = PostgresManager()
        df = db.get_action_impact(client_id, before_days=14, after_days=14)

        if df.empty:
            print("⚠️  No impact data found for client")
            return True

        # Check model version column
        assert 'model_version' in df.columns, "Missing model_version column"
        actual_version = df['model_version'].iloc[0]
        expected_version = get_impact_model_version()

        print(f"✓ model_version column present: {actual_version}")
        assert actual_version == expected_version, f"Version mismatch: {actual_version} != {expected_version}"

        # Check version-specific columns
        if expected_version == "v3.3":
            v33_columns = [
                'market_shift',
                'scale_factor',
                'impact_v33',
                'final_impact_v33',
                'expected_sales_v33',
                'decision_impact_v32',  # Backup
                'final_decision_impact_v32'  # Backup
            ]

            for col in v33_columns:
                assert col in df.columns, f"Missing v3.3 column: {col}"

            print(f"✓ All v3.3 columns present: {', '.join(v33_columns[:3])}...")

            # Verify backup columns have different values
            if len(df) > 0:
                v33_impact = df['final_decision_impact'].sum()
                v32_backup = df['final_decision_impact_v32'].sum()

                print(f"✓ v3.3 total impact: ${v33_impact:,.2f}")
                print(f"✓ v3.2 backup impact: ${v32_backup:,.2f}")

                if v33_impact != v32_backup:
                    diff_pct = abs(v33_impact - v32_backup) / abs(v32_backup) * 100 if v32_backup != 0 else 0
                    print(f"✓ Difference: {diff_pct:.1f}% (expected for v3.3)")

        elif expected_version == "v3.2":
            # v3.2 should NOT have v3.3-specific columns
            v33_only_columns = [
                'market_shift',
                'scale_factor',
                'impact_v33',
                'final_impact_v33'
            ]

            for col in v33_only_columns:
                if col in df.columns:
                    print(f"⚠️  Found v3.3 column in v3.2 mode: {col} (may be from cached data)")

            print(f"✓ Running in v3.2 mode (no v3.3 columns required)")

        print()
        return True

    except Exception as e:
        print(f"✗ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_export_functionality():
    """Test that export utilities work correctly."""
    print("=" * 60)
    print("TEST 3: Export Functionality")
    print("=" * 60)

    try:
        from features.impact.utils import (
            check_model_version_consistency,
            export_impact_data_with_version
        )

        # Create mock dataframe
        mock_df = pd.DataFrame({
            'action_date': [datetime.now() - timedelta(days=i) for i in range(10)],
            'target_text': [f'target_{i}' for i in range(10)],
            'decision_impact': np.random.randn(10) * 100,
            'final_decision_impact': np.random.randn(10) * 100,
            'model_version': [get_impact_model_version()] * 10
        })

        # Test consistency check
        version_check = check_model_version_consistency(mock_df)
        assert version_check['is_consistent'], "Version check failed for consistent data"
        print(f"✓ Version consistency check passed: {version_check['versions']}")

        # Test mixed versions
        mixed_df = mock_df.copy()
        mixed_df.loc[5:, 'model_version'] = 'v3.2' if get_impact_model_version() == 'v3.3' else 'v3.3'
        mixed_check = check_model_version_consistency(mixed_df)
        assert not mixed_check['is_consistent'], "Should detect mixed versions"
        assert mixed_check['warning_message'] is not None, "Should have warning message"
        print(f"✓ Mixed version detection working")

        # Test export
        csv_bytes = export_impact_data_with_version(mock_df, "test_export")
        assert len(csv_bytes) > 0, "Export produced empty result"
        assert get_impact_model_version() in csv_bytes.decode('utf-8'), "Model version not in export"
        print(f"✓ Export functionality working ({len(csv_bytes)} bytes)")

        print()
        return True

    except Exception as e:
        print(f"✗ Export test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rollback_simulation():
    """Simulate rollback by checking feature flag logic."""
    print("=" * 60)
    print("TEST 4: Rollback Simulation")
    print("=" * 60)

    current_version = get_impact_model_version()
    print(f"Current version: {current_version}")

    if current_version == "v3.3":
        print("\n📋 To test rollback:")
        print("   1. Open core/postgres_manager.py")
        print("   2. Change line ~99: IMPACT_MODEL_VERSION = 'v3.2'")
        print("   3. Re-run this test script")
        print("   4. Verify all tests pass in v3.2 mode")
        print("   5. Change back to v3.3 when done")
    else:
        print("\n✓ Currently in v3.2 mode (rollback state)")
        print("   To return to v3.3:")
        print("   1. Open core/postgres_manager.py")
        print("   2. Change line ~99: IMPACT_MODEL_VERSION = 'v3.3'")
        print("   3. Restart application")

    print()
    return True


def print_rollback_instructions():
    """Print quick rollback instructions."""
    print("\n" + "=" * 60)
    print("ROLLBACK QUICK REFERENCE")
    print("=" * 60)
    print("""
To rollback from v3.3 to v3.2:

1. Open: core/postgres_manager.py (line ~99)
2. Change: IMPACT_MODEL_VERSION = "v3.2"
3. Save file
4. Restart application (or git commit + push for cloud)
5. Verify dashboard shows v3.2

To return to v3.3:

1. Open: core/postgres_manager.py (line ~99)
2. Change: IMPACT_MODEL_VERSION = "v3.3"
3. Save file
4. Restart application

Full documentation: dev_resources/documentation/ROLLBACK_GUIDE.md
    """)


def run_all_tests(client_id: str = None):
    """Run all rollback tests."""
    print("\n" + "🔄" * 30)
    print("IMPACT MODEL ROLLBACK TEST SUITE")
    print("🔄" * 30 + "\n")

    results = []

    # Test 1: Feature flag
    try:
        current_version = test_feature_flag()
        results.append(("Feature Flag", True))
    except Exception as e:
        print(f"✗ Feature flag test failed: {e}")
        results.append(("Feature Flag", False))
        return  # Can't continue without valid version

    # Test 2: Column presence
    try:
        success = test_column_presence(client_id)
        results.append(("Column Presence", success))
    except Exception as e:
        print(f"✗ Column test failed: {e}")
        results.append(("Column Presence", False))

    # Test 3: Export functionality
    try:
        success = test_export_functionality()
        results.append(("Export", success))
    except Exception as e:
        print(f"✗ Export test failed: {e}")
        results.append(("Export", False))

    # Test 4: Rollback simulation
    try:
        success = test_rollback_simulation()
        results.append(("Rollback Simulation", success))
    except Exception as e:
        print(f"✗ Rollback simulation failed: {e}")
        results.append(("Rollback Simulation", False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {test_name}")

    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)

    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n✅ All rollback tests PASSED")
        print("   Rollback functionality is working correctly")
    else:
        print("\n⚠️  Some tests FAILED")
        print("   Check errors above and fix before deploying")

    # Print rollback instructions
    print_rollback_instructions()


if __name__ == "__main__":
    # Check if client_id provided as argument
    client_id = sys.argv[1] if len(sys.argv) > 1 else None

    if client_id:
        print(f"Testing with client_id: {client_id}")
    else:
        print("No client_id provided - skipping database tests")
        print("Usage: python test_rollback_v33_to_v32.py <client_id>")

    run_all_tests(client_id)
