
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

    # Read SQL file
    with open('desktop/db/migrations/003_add_bsr_history.sql', 'r') as f:
        sql_content = f.read()

    print("Executing migration...")
    cur.execute(sql_content)
    conn.commit()
    print("Migration executed successfully.")

    cur.close()
    conn.close()

except Exception as e:
    print(f"Migration failed: {e}")
    exit(1)
