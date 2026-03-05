import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def alter_table():
    print("Altering table actions_log...")
    conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
    conn.autocommit = True
    with conn.cursor() as cursor:
        cursor.execute("SET statement_timeout = 60000;")
        cursor.execute("""
            ALTER TABLE actions_log 
            ADD COLUMN IF NOT EXISTS outcome_roas_delta FLOAT,
            ADD COLUMN IF NOT EXISTS outcome_label VARCHAR(50),
            ADD COLUMN IF NOT EXISTS outcome_evaluated_at TIMESTAMP;
        """)
    print("Added outcome columns successfully.")
    conn.close()

if __name__ == "__main__":
    alter_table()
