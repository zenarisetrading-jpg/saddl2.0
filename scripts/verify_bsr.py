
import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv(Path('.env'))

database_url = os.environ.get('DATABASE_URL_DIRECT')
if not database_url:
    print("DATABASE_URL_DIRECT not found in .env")
    exit(1)

try:
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    print("Verifying sc_raw.bsr_history...")
    try:
        cur.execute("SELECT COUNT(*) FROM sc_raw.bsr_history")
        count = cur.fetchone()[0]
        print(f"sc_raw.bsr_history count: {count}")
    except Exception as e:
        print(f"Failed to query sc_raw.bsr_history: {e}")
        conn.rollback()

    print("\nVerifying sc_analytics.bsr_trends...")
    try:
        cur.execute("SELECT * FROM sc_analytics.bsr_trends LIMIT 5")
        rows = cur.fetchall()
        print(f"sc_analytics.bsr_trends rows: {len(rows)}")
        for row in rows:
            print(row)
    except Exception as e:
        print(f"Failed to query sc_analytics.bsr_trends: {e}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"Connection failed: {e}")
