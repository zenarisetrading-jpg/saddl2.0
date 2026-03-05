import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def kill_idle():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE state IN ('idle', 'idle in transaction') 
            AND pid <> pg_backend_pid();
        """)
        print("Terminated idle connections.")
    conn.close()

if __name__ == "__main__":
    kill_idle()
