import os
import logging
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "sugarcane_harvests"),
    "user": os.getenv("DB_USER", "sugarcane_users"),
    "password": os.getenv("DB_PASSWORD", "secure_password_123"),
    "port": int(os.getenv("DB_PORT", 5432))
}

db_pool = None

def init_db():
    global db_pool
    try:
        conninfo = f"host={DB_CONFIG['host']} dbname={DB_CONFIG['database']} user={DB_CONFIG['user']} password={DB_CONFIG['password']} port={DB_CONFIG['port']}"
        db_pool = ConnectionPool(conninfo, min_size=1, max_size=10)
        logger.info("✓ Database pool created")
    except Exception as e:
        logger.error(f"✗ DB pool failed: {e}")

def get_db_conn():
    if db_pool:
        return db_pool.getconn()
    return None

def release_db_conn(conn):
    if db_pool and conn:
        db_pool.putconn(conn)
