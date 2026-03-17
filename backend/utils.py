import hashlib
import secrets
import logging
from psycopg.rows import dict_row
from db import get_db_conn, release_db_conn

logger = logging.getLogger(__name__)

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    """Generate random session token"""
    return secrets.token_hex(32)

def verify_token(token):
    """Verify session token and return user"""
    if not token:
        return None
        
    conn = None
    try:
        conn = get_db_conn()
        if not conn:
            return None
        cur = conn.cursor(row_factory=dict_row)
        
        cur.execute("""
            SELECT user_id, name, phone, role, factory_id
            FROM users
            WHERE session_token = %s
        """, (token,))
        
        user = cur.fetchone()
        cur.close()
        return user
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None
    finally:
        if conn:
            release_db_conn(conn)
