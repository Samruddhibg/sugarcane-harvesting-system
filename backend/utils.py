import hashlib
import secrets
import logging
import os
from datetime import datetime, timedelta

import jwt
from psycopg.rows import dict_row
from db import get_db_conn, release_db_conn

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_THIS_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXP_DELTA_HOURS = int(os.getenv("JWT_EXP_DELTA_HOURS", 12))


def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token():
    """Generate random session token"""
    return secrets.token_hex(32)


def generate_jwt_token(user_id, role, factory_id=None, expires_hours=JWT_EXP_DELTA_HOURS):
    """Generate a signed JWT access token."""
    now = datetime.utcnow()
    exp = now + timedelta(hours=expires_hours)
    payload = {
        "sub": user_id,
        "role": role,
        "factory_id": factory_id,
        "iat": now,
        "exp": exp,
        "jti": secrets.token_hex(16)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def verify_jwt_token(token):
    """Verify JWT signature and expiration."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
    return None


def get_auth_token(request):
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return auth_header.strip()


def get_authenticated_user(request, allowed_roles=None):
    """Verify request bearer token and optionally enforce role(s)."""
    token = get_auth_token(request)
    if not token:
        return None

    user = verify_token(token)
    if not user:
        return None

    if allowed_roles:
        if isinstance(allowed_roles, str):
            allowed_roles = [allowed_roles]
        if user.get("role") not in allowed_roles:
            return None

    return user


def verify_token(token):
    """Verify token and return user metadata if authorized."""
    if not token:
        return None

    payload = verify_jwt_token(token)
    conn = None
    try:
        conn = get_db_conn()
        if not conn:
            return None
        cur = conn.cursor(row_factory=dict_row)

        if payload:
            cur.execute("""
                SELECT user_id, name, phone, role, factory_id
                FROM users
                WHERE user_id = %s AND session_token = %s
            """, (payload["sub"], token))
        else:
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


def calculate_haversine_distance(a, b):
    """Calculate distance in kilometers between two points (lat, lon). Returns float."""
    try:
        from math import radians, cos, sin, asin, sqrt
        lat1, lon1 = float(a[0]), float(a[1])
        lat2, lon2 = float(b[0]), float(b[1])
        # haversine
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        lat1r = radians(lat1)
        lat2r = radians(lat2)
        a_h = sin(dlat/2)**2 + cos(lat1r) * cos(lat2r) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a_h))
        km = 6371 * c
        return round(km, 2)
    except Exception:
        return 0.0
