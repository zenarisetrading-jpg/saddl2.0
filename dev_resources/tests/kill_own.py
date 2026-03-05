import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def kill_own():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    conn.autocommit = True
    with conn.cursor() as cur:
        # Cancel queries first
        cur.execute("""
            SELECT pg_cancel_backend(pid) 
            FROM pg_stat_activity 
            WHERE state != 'idle' 
            AND pid <> pg_backend_pid()
            AND usename = current_user;
        """)
        # Terminate backends
        cur.execute("""
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE pid <> pg_backend_pid()
            AND usename = current_user;
        """)
        print("Terminated own connections.")
    conn.close()

if __name__ == "__main__":
    kill_own()
