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
        # Check a specific failing ID from the screenshot: 39476485956638
        print("Checking ID: 39476485956638 (Product Targeting Id)")
        
        # Look in bulk_id_mapping
        cur.execute("""
            SELECT "Campaign Name", "Ad Group Name", "Targeting Expression", "Targeting Id" 
            FROM bulk_id_mapping 
            WHERE "Targeting Id" LIKE '%39476485956638%'
        """)
        bulk_matches = cur.fetchall()
        print(f"Bulk Mapping matches: {len(bulk_matches)}")
        for row in bulk_matches:
            print(f"  {row}")
            
        print("\nChecking ID: 60482809592092 (Keyword Id)")
        cur.execute("""
            SELECT "Campaign Name", "Ad Group Name", "Keyword Text", "Keyword Id" 
            FROM bulk_id_mapping 
            WHERE "Keyword Id" LIKE '%60482809592092%'
        """)
        kw_matches = cur.fetchall()
        for row in kw_matches:
            print(f"  {row}")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.release_connection(conn)
