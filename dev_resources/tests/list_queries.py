import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def list_queries():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pid, state, wait_event_type, wait_event, query
            FROM pg_stat_activity
            WHERE pid <> pg_backend_pid();
        """)
        for row in cur.fetchall():
            print(row)
    conn.close()

if __name__ == "__main__":
    list_queries()
