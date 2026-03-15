import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
try:
    conninfo = f"host=localhost dbname=sugarcane_harvest user=sugarcane_user password=secure_password_123 port=5432"
    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            tables = cur.fetchall()
            print(f'Tables found: {[t[0] for t in tables]}')
except Exception as e:
    print(f'Error: {e}')
