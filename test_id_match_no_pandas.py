import sys
import os

app_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if app_path not in sys.path:
    sys.path.append(app_path)

from app_core.db_manager import DatabaseManager
db = DatabaseManager()
conn = db.get_connection()

try:
    with conn.cursor() as cur:
        # We need to find out why TargetingExpression "loose-match" was assigned TargetingId 39476485956638
        print("--- ID: 39476485956638 ---")
        cur.execute("""
            SELECT "Campaign Name", "Ad Group Name", "Targeting Expression", "Targeting Id"
            FROM bulk_id_mapping 
            WHERE "Targeting Id" LIKE '%39476485956638%'
        """)
        for row in cur.fetchall(): print(f"BULK: {row}")

        cur.execute("""
            SELECT "Campaign Name", "Ad Group Name", "Targeting", "TargetingId"
            FROM target_stats 
            WHERE "TargetingId" LIKE '%39476485956638%'
            LIMIT 5
        """)
        for row in cur.fetchall(): print(f"STATS: {row}")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.release_connection(conn)
