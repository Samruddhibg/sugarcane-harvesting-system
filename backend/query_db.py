import os
import psycopg
from psycopg.rows import dict_row

conninfo = "host=localhost dbname=sugarcane_harvests user=sugarcane_users password=secure_password_123 port=5432"

try:
    with psycopg.connect(conninfo) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            print("--- USERS ---")
            cur.execute("SELECT user_id, name, role, factory_id FROM users LIMIT 5;")
            for row in cur.fetchall():
                print(row)
                
            print("\n--- f_register schema ---")
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'f_register';
            """)
            for row in cur.fetchall():
                print(row)
                
            print("\n--- f_register data ---")
            cur.execute("SELECT f_id, user_id, f_factory FROM f_register LIMIT 5;")
            for row in cur.fetchall():
                print(row)
                
            print("\n--- m_register schema ---")
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'm_register';
            """)
            for row in cur.fetchall():
                print(row)
                
            print("\n--- m_register data ---")
            cur.execute("SELECT m_id, user_id, m_factory FROM m_register LIMIT 5;")
            for row in cur.fetchall():
                print(row)
                
except Exception as e:
    print(f'Error: {e}')
