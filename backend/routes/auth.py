from flask import Blueprint, request, jsonify
import logging
from psycopg.rows import dict_row
from db import get_db_conn, release_db_conn
from utils import hash_password, generate_token

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route("/signup", methods=["POST"])
def signup():
    """User signup - farmer, machine_owner, or factory_admin"""
    data = request.json
    required = ['name', 'phone', 'password', 'role', 'factory_id']
    
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400
    
    if data['role'] not in ['farmer', 'machine_owner', 'factory_admin']:
        return jsonify({"error": "Invalid role"}), 400
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Check if phone already exists
        cur.execute("SELECT user_id FROM users WHERE phone = %s", (data['phone'],))
        if cur.fetchone():
            return jsonify({"error": "Phone number already registered"}), 409
        
        # Create user
        password_hash = hash_password(data['password'])
        token = generate_token()
        
        cur.execute("""
            INSERT INTO users (name, phone, password_hash, role, factory_id, session_token)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id, name, role, factory_id
        """, (data['name'], data['phone'], password_hash, data['role'], 
              data['factory_id'], token))
        
        user = cur.fetchone()
        conn.commit()
        cur.close()
        
        logger.info(f"✓ New signup: {data['name']} ({data['role']})")
        
        return jsonify({
            "status": "success",
            "user_id": user[0],
            "name": user[1],
            "role": user[2],
            "factory_id": user[3],
            "token": token
        }), 201
        
    except Exception as e:
        logger.error(f"Signup error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@auth_bp.route("/login", methods=["POST"])
def login():
    """User login"""
    data = request.json
    required = ['phone', 'password']
    
    if not all(k in data for k in required):
        return jsonify({"error": "Missing phone or password"}), 400
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(row_factory=dict_row)
        
        password_hash = hash_password(data['password'])
        
        cur.execute("""
            SELECT user_id, name, phone, role, factory_id
            FROM users 
            WHERE phone = %s AND password_hash = %s
        """, (data['phone'], password_hash))
        
        user = cur.fetchone()
        
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Generate new token
        token = generate_token()
        cur.execute("""
            UPDATE users SET session_token = %s, last_login = NOW()
            WHERE user_id = %s
        """, (token, user['user_id']))
        
        conn.commit()
        cur.close()
        
        logger.info(f"✓ Login: {user['name']} ({user['role']})")
        
        return jsonify({
            "status": "success",
            "user_id": user['user_id'],
            "name": user['name'],
            "phone": user['phone'],
            "role": user['role'],
            "factory_id": user['factory_id'],
            "token": token
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """User logout"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not token:
        return jsonify({"error": "No token provided"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE users SET session_token = NULL
            WHERE session_token = %s
        """, (token,))
        
        conn.commit()
        cur.close()
        
        return jsonify({"status": "success", "message": "Logged out"}), 200
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)
