
import unittest
import pandas as pd
from datetime import date
import sys
import os

# Adjust path to import db_manager (Result: /.../saddle/)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
from desktop.core.db_manager import DatabaseManager

class TestHarvestImpactLogic(unittest.TestCase):
    
    def setUp(self):
        # We will mock the database manager methods or use a temporary DB
        # Since logic is inside get_action_impact, we need to mock the internal SQL returns
        # But DatabaseManager._get_connection usage makes mocking hard without a real DB file.
        # So we will create a temporary SQLite DB for the test.
        self.test_db_path = "test_harvest_impact.db"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
            
        self.db = DatabaseManager(self.test_db_path)
        self.client_id = "test_client"
        self.before_date = "2024-01-01"
        self.after_date = "2024-02-01"
        self.action_date = "2024-01-15"

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    def test_harvest_winner(self):
        # 1. Seed Stats (Before & After) using DataFrame
        # Source Term (Before)
        df_source = pd.DataFrame([{
            'Start Date': self.before_date,
            'Campaign Name': 'Source_Campaign',
            'Ad Group Name': 'AG1',
            'Customer Search Term': 'test_winner', # Use CST for harvest matching
            'Match Type': '-', 
            'Spend': 100.0,
            'Sales': 400.0,
            'Orders': 10,
            'Clicks': 100,
            'Impressions': 1000
        }])
        self.db.save_target_stats_batch(df_source, self.client_id)
        
        # Destination Term (After) - Winner
        df_dest = pd.DataFrame([{
            'Start Date': self.after_date,
            'Campaign Name': 'New_Exact_Campaign_Winner',
            'Ad Group Name': 'AG1',
            'Customer Search Term': 'test_winner', # CST matches target
            'Keyword Text': 'test_winner', # Target matches CST
            'Match Type': 'Exact',
            'Spend': 200.0,
            'Sales': 900.0, 
            'Orders': 20,
            'Clicks': 200,
            'Impressions': 2000
        }])
        self.db.save_target_stats_batch(df_dest, self.client_id)

        # 2. Seed Action
        with self.db._get_connection() as conn:
            conn.execute("""
                INSERT INTO actions_log 
                (client_id, action_date, action_type, target_text, campaign_name, new_campaign_name, batch_id)
                VALUES (?, ?, 'HARVEST', ?, ?, ?, 'batch_123')
            """, (self.client_id, self.action_date, 'test_winner', 'Source_Campaign', 'New_Exact_Campaign_Winner'))

        # 3. Calculate Impact
        df = self.db.get_action_impact(self.client_id)
        
        print("\n--- Test Case 1: Winner ---")
        if not df.empty:
            print(df[['target_text', 'impact_score', 'after_sales', 'before_sales']].to_string())
            row = df.iloc[0]
            # logic: Expected Efficiency = 4.0 * 0.85 = 3.4
            # Expected Sales = 200 * 3.4 = 680
            # Impact = 900 - 680 = 220
            self.assertAlmostEqual(row['impact_score'], 220.0, delta=1.0)
            self.assertEqual(row['attribution'], 'harvest_realized')
        else:
            self.fail("No impact results returned")

    def test_harvest_baseline(self):
        # 1. Seed Stats
        # Source (Before)
        df_source = pd.DataFrame([{
            'Start Date': self.before_date,
            'Campaign Name': 'Source_Campaign',
            'Ad Group Name': 'AG1',
            'Customer Search Term': 'test_baseline',
            'Match Type': '-',
            'Spend': 100.0,
            'Sales': 400.0,
            'Orders': 10
        }])
        self.db.save_target_stats_batch(df_source, self.client_id)
        
        # Destination (After) - Exact Baseline (3.4 ROAS)
        df_dest = pd.DataFrame([{
            'Start Date': self.after_date,
            'Campaign Name': 'New_Exact_Campaign_Baseline',
            'Ad Group Name': 'AG1',
            'Customer Search Term': 'test_baseline',
            'Match Type': 'Exact',
            'Spend': 200.0,
            'Sales': 680.0,
            'Orders': 15
        }])
        self.db.save_target_stats_batch(df_dest, self.client_id)

        # 2. Seed Action
        with self.db._get_connection() as conn:
            conn.execute("""
                INSERT INTO actions_log 
                (client_id, action_date, action_type, target_text, campaign_name, new_campaign_name, batch_id)
                VALUES (?, ?, 'HARVEST', ?, ?, ?, 'batch_123')
            """, (self.client_id, self.action_date, 'test_baseline', 'Source_Campaign', 'New_Exact_Campaign_Baseline'))

        # 3. Calculate
        df = self.db.get_action_impact(self.client_id)
        
        print("\n--- Test Case 2: Baseline (Net 0) ---")
        if not df.empty:
            print(df[['target_text', 'impact_score']].to_string())
            row = df[df['target_text'] == 'test_baseline'].iloc[0]
            self.assertAlmostEqual(row['impact_score'], 0.0, delta=1.0)
        else:
            self.fail("No impact result")

    def test_harvest_ghost(self):
        # 1. Seed Stats
        # Source (Before)
        df_source = pd.DataFrame([{
            'Start Date': self.before_date,
            'Campaign Name': 'Source_Campaign',
            'Ad Group Name': 'AG1',
            'Customer Search Term': 'test_ghost',
            'Match Type': '-',
            'Spend': 100.0,
            'Sales': 400.0,
            'Orders': 10
        }])
        self.db.save_target_stats_batch(df_source, self.client_id)
        
        # Destination (After) - Ghost (Record exists but 0 sales/spend)
        # Note: save_target_stats_batch logic might skip if no target_col found, but we provide Customer Search Term
        df_dest = pd.DataFrame([{
            'Start Date': self.after_date,
            'Campaign Name': 'New_Exact_Campaign_Ghost',
            'Ad Group Name': 'AG1',
            'Customer Search Term': 'test_ghost',
            'Match Type': 'Exact',
            'Spend': 0.0,
            'Sales': 0.0,
            'Orders': 0,
            'Clicks': 0,
            'Impressions': 0
        }])
        self.db.save_target_stats_batch(df_dest, self.client_id)

        # 2. Seed Action
        with self.db._get_connection() as conn:
            conn.execute("""
                INSERT INTO actions_log 
                (client_id, action_date, action_type, target_text, campaign_name, new_campaign_name, batch_id)
                VALUES (?, ?, 'HARVEST', ?, ?, ?, 'batch_123')
            """, (self.client_id, self.action_date, 'test_ghost', 'Source_Campaign', 'New_Exact_Campaign_Ghost'))

        # 3. Calculate
        df = self.db.get_action_impact(self.client_id)
        
        print("\n--- Test Case 3: Ghost ---")
        if not df.empty:
            print(df[['target_text', 'impact_score', 'validation_status']].to_string())
            row = df[df['target_text'] == 'test_ghost'].iloc[0]
            self.assertEqual(row['impact_score'], 0.0)
            self.assertIn("Ghost", row['validation_status'])
        else:
            self.fail("No impact result")

if __name__ == '__main__':
    unittest.main()
