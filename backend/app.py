#!/usr/bin/env python3
"""
Complete Sugarcane Harvesting System - Backend with Authentication
Flask API + PostgreSQL
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta, date
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from collections import deque
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import hashlib
import secrets
import urllib.parse
from utils import generate_jwt_token, verify_token, get_authenticated_user, get_auth_token

# ==================== CONFIGURATION ====================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    urllib.parse.uses_netloc.append("postgres")
    url = urllib.parse.urlparse(DATABASE_URL)
    DB_CONFIG = {
        "database": url.path[1:],
        "user": url.username,
        "password": url.password,
        "host": url.hostname,
        "port": url.port,
        "sslmode": "require"
    }
else:
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME", "sugarcane_harvest"),
        "user": os.getenv("DB_USER", "sugarcane_users"),
        "password": os.getenv("DB_PASSWORD", "secure_password_123"),
        "port": int(os.getenv("DB_PORT", 5432))
    }

# Constants
MATURITY_DAYS = 450
NEARLY_MATURE_DAYS = 400
FACTORY_IDS = list(range(1, 8))
ACCEPTANCE_TIMEOUT_HOURS = 12

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# ==================== DATABASE POOL ====================

try:
    db_pool = pool.SimpleConnectionPool(1, 10, **DB_CONFIG)
    logger.info("Database pool created successfully")
except Exception as e:
    logger.error(f"DB pool failed: {e}")
    db_pool = None

def get_db_conn():
    if db_pool is None:
        raise Exception("Database connection pool is not initialized. Check PostgreSQL is running and credentials are correct.")
    return db_pool.getconn()

def release_db_conn(conn):
    if db_pool is not None and conn is not None:
        db_pool.putconn(conn)

# ==================== AUTO-CREATE TABLES ====================

def init_tables():
    """Automatically create tables if they don't exist."""
    if db_pool is None:
        logger.error("Cannot init tables - no database connection")
        return
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Check if tables exist
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'users';
        """)
        if cur.fetchone():
            logger.info("Database tables already exist - skipping init")
            cur.close()
            return
        
        logger.info("Tables not found - creating database schema...")
        
        # Create all tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS factories (
                factory_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                location VARCHAR(255) NOT NULL,
                daily_capacity INT NOT NULL
            );
            
            INSERT INTO factories (factory_id, name, location, daily_capacity) VALUES
            (1, 'Factory Alpha', 'North Zone', 500000),
            (2, 'Factory Beta', 'South Zone', 750000),
            (3, 'Factory Gamma', 'East Zone', 600000),
            (4, 'Factory Delta', 'West Zone', 400000),
            (5, 'Factory Epsilon', 'Central Zone', 550000),
            (6, 'Factory Zeta', 'North-East Zone', 480000),
            (7, 'Factory Eta', 'South-West Zone', 520000)
            ON CONFLICT (factory_id) DO NOTHING;
            
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                phone VARCHAR(20) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL,
                factory_id INT,
                session_token TEXT,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                CONSTRAINT fk_users_factory FOREIGN KEY (factory_id) REFERENCES factories(factory_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
            CREATE INDEX IF NOT EXISTS idx_users_token ON users(session_token);
            CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
            
            CREATE TABLE IF NOT EXISTS f_register (
                f_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(user_id),
                f_name VARCHAR(255) NOT NULL,
                f_phone_number VARCHAR(20) NOT NULL,
                f_factory INT NOT NULL REFERENCES factories(factory_id),
                f_address TEXT NOT NULL,
                f_district VARCHAR(100) NOT NULL,
                f_planting_date DATE NOT NULL,
                f_crop INT NOT NULL,
                f_submission_date DATE NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_f_user ON f_register(user_id);
            CREATE INDEX IF NOT EXISTS idx_f_factory ON f_register(f_factory);
            CREATE INDEX IF NOT EXISTS idx_f_status ON f_register(status);
            CREATE INDEX IF NOT EXISTS idx_f_planting ON f_register(f_planting_date);
            
            CREATE TABLE IF NOT EXISTS m_register (
                m_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(user_id),
                m_name VARCHAR(255) NOT NULL,
                m_phone_number VARCHAR(20) NOT NULL,
                m_factory INT NOT NULL REFERENCES factories(factory_id),
                m_address TEXT NOT NULL,
                m_district VARCHAR(100) NOT NULL,
                m_status VARCHAR(20) DEFAULT 'idle',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_m_user ON m_register(user_id);
            CREATE INDEX IF NOT EXISTS idx_m_factory ON m_register(m_factory);
            CREATE INDEX IF NOT EXISTS idx_m_status ON m_register(m_status);
            
            CREATE TABLE IF NOT EXISTS assignment_requests (
                assignment_request_id SERIAL PRIMARY KEY,
                factory_id INT NOT NULL REFERENCES factories(factory_id),
                farmer_id INT NOT NULL REFERENCES f_register(f_id),
                machine_id INT NOT NULL REFERENCES m_register(m_id),
                scheduled_date DATE NOT NULL,
                estimated_harvest_days INT NOT NULL,
                estimated_completion DATE NOT NULL,
                production_kg DECIMAL(10, 2) NOT NULL,
                priority VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                request_sent_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_ar_farmer ON assignment_requests(farmer_id);
            CREATE INDEX IF NOT EXISTS idx_ar_machine ON assignment_requests(machine_id);
            CREATE INDEX IF NOT EXISTS idx_ar_status ON assignment_requests(status);
            CREATE INDEX IF NOT EXISTS idx_ar_expires ON assignment_requests(expires_at);
            
            CREATE TABLE IF NOT EXISTS confirmed_assignments (
                assignment_id SERIAL PRIMARY KEY,
                factory_id INT NOT NULL REFERENCES factories(factory_id),
                farmer_id INT NOT NULL REFERENCES f_register(f_id),
                machine_id INT NOT NULL REFERENCES m_register(m_id),
                assigned_date DATE NOT NULL,
                estimated_harvest_days INT NOT NULL,
                estimated_completion DATE NOT NULL,
                production_kg DECIMAL(10, 2) NOT NULL,
                status VARCHAR(20) DEFAULT 'assigned',
                actual_completion_date DATE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_ca_farmer ON confirmed_assignments(farmer_id);
            CREATE INDEX IF NOT EXISTS idx_ca_machine ON confirmed_assignments(machine_id);
            CREATE INDEX IF NOT EXISTS idx_ca_factory ON confirmed_assignments(factory_id);
            CREATE INDEX IF NOT EXISTS idx_ca_date ON confirmed_assignments(assigned_date);
            
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL REFERENCES users(user_id),
                user_type VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT NOW(),
                read_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id);
            CREATE INDEX IF NOT EXISTS idx_notif_sent ON notifications(sent_at);
            
            CREATE OR REPLACE FUNCTION update_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            
            DROP TRIGGER IF EXISTS trg_users_timestamp ON users;
            CREATE TRIGGER trg_users_timestamp BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION update_timestamp();
            
            DROP TRIGGER IF EXISTS trg_f_register_timestamp ON f_register;
            CREATE TRIGGER trg_f_register_timestamp BEFORE UPDATE ON f_register
            FOR EACH ROW EXECUTE FUNCTION update_timestamp();
            
            DROP TRIGGER IF EXISTS trg_m_register_timestamp ON m_register;
            CREATE TRIGGER trg_m_register_timestamp BEFORE UPDATE ON m_register
            FOR EACH ROW EXECUTE FUNCTION update_timestamp();
            
            DROP TRIGGER IF EXISTS trg_assignment_requests_timestamp ON assignment_requests;
            CREATE TRIGGER trg_assignment_requests_timestamp BEFORE UPDATE ON assignment_requests
            FOR EACH ROW EXECUTE FUNCTION update_timestamp();
            
            DROP TRIGGER IF EXISTS trg_confirmed_assignments_timestamp ON confirmed_assignments;
            CREATE TRIGGER trg_confirmed_assignments_timestamp BEFORE UPDATE ON confirmed_assignments
            FOR EACH ROW EXECUTE FUNCTION update_timestamp();
        """)
        
        conn.commit()
        logger.info("All database tables created successfully!")
        cur.close()
        
    except Exception as e:
        logger.error(f"Table initialization failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_conn(conn)

# Run table init on startup
init_tables()

# ==================== AUTHENTICATION ====================

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

@app.route("/api/auth/signup", methods=["POST"])
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
        
        password_hash = hash_password(data['password'])
        cur.execute("""
            INSERT INTO users (name, phone, password_hash, role, factory_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id, name, role, factory_id
        """, (data['name'], data['phone'], password_hash, data['role'], data['factory_id']))
        
        user = cur.fetchone()
        if not user:
            raise Exception("Failed to create user")

        token = generate_jwt_token(user[0], user[2], user[3])
        cur.execute("""
            UPDATE users SET session_token = %s, last_login = NOW()
            WHERE user_id = %s
        """, (token, user[0]))
        
        conn.commit()
        cur.close()
        
        logger.info(f"New signup: {data['name']} ({data['role']})")
        
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

@app.route("/api/auth/login", methods=["POST"])
def login():
    """User login"""
    data = request.json
    required = ['phone', 'password']
    
    if not all(k in data for k in required):
        return jsonify({"error": "Missing phone or password"}), 400
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        password_hash = hash_password(data['password'])
        
        cur.execute("""
            SELECT user_id, name, phone, role, factory_id
            FROM users 
            WHERE phone = %s AND password_hash = %s
        """, (data['phone'], password_hash))
        
        user = cur.fetchone()
        
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        
        token = generate_jwt_token(user['user_id'], user['role'], user['factory_id'])
        cur.execute("""
            UPDATE users SET session_token = %s, last_login = NOW()
            WHERE user_id = %s
        """, (token, user['user_id']))
        
        conn.commit()
        cur.close()
        
        logger.info(f"Login: {user['name']} ({user['role']})")
        
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

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """User logout"""
    token = get_auth_token(request)
    
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

# ==================== FARMER ENDPOINTS ====================

@app.route("/api/farmer/register-crop", methods=["POST"])
def farmer_register_crop():
    """Farmer registers a new crop"""
    user = get_authenticated_user(request, 'farmer')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    required = ['address', 'district', 'planting_date', 'crop_acres']
    
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO f_register (
                user_id, f_name, f_phone_number, f_factory, f_address, 
                f_district, f_planting_date, f_crop, f_submission_date, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            RETURNING f_id
        """, (
            user['user_id'], user['name'], user['phone'], user['factory_id'],
            data['address'], data['district'], data['planting_date'],
            data['crop_acres'], date.today()
        ))
        
        f_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        logger.info(f" Crop registered: Farmer {user['name']} - {data['crop_acres']} acres")
        
        return jsonify({
            "status": "success",
            "f_id": f_id,
            "message": "Crop registered successfully"
        }), 201
        
    except Exception as e:
        logger.error(f"Crop registration error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@app.route("/api/farmer/dashboard", methods=["GET"])
def farmer_dashboard():
    """Get farmer dashboard data"""
    user = get_authenticated_user(request, 'farmer')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get crops
        cur.execute("""
            SELECT f_id, f_crop, f_planting_date, f_submission_date, status,
                   (CURRENT_DATE - f_planting_date) as days_since_planting
            FROM f_register
            WHERE user_id = %s
            ORDER BY f_submission_date DESC
        """, (user['user_id'],))
        crops = cur.fetchall()
        
        # Get assignment requests
        cur.execute("""
            SELECT ar.*, m.m_name as machine_owner, f.f_crop
            FROM assignment_requests ar
            JOIN f_register f ON ar.farmer_id = f.f_id
            LEFT JOIN m_register m ON ar.machine_id = m.m_id
            WHERE f.user_id = %s
            ORDER BY ar.request_sent_at DESC
            LIMIT 10
        """, (user['user_id'],))
        requests_list = cur.fetchall()
        
        # Get confirmed assignments
        cur.execute("""
            SELECT ca.*, m.m_name as machine_owner, f.f_crop
            FROM confirmed_assignments ca
            JOIN f_register f ON ca.farmer_id = f.f_id
            LEFT JOIN m_register m ON ca.machine_id = m.m_id
            WHERE f.user_id = %s
            ORDER BY ca.assigned_date DESC
            LIMIT 10
        """, (user['user_id'],))
        assignments = cur.fetchall()
        
        # Convert dates
        for item in crops + requests_list + assignments:
            for k, v in item.items():
                if isinstance(v, (date, datetime)):
                    item[k] = v.isoformat()
        
        cur.close()
        
        return jsonify({
            "user": {
                "name": user['name'],
                "phone": user['phone'],
                "factory_id": user['factory_id']
            },
            "crops": crops,
            "pending_requests": [r for r in requests_list if r['status'] == 'pending'],
            "assignments": assignments,
            "stats": {
                "total_crops": len(crops),
                "pending_crops": len([c for c in crops if c['status'] == 'pending']),
                "assigned_crops": len([c for c in crops if c['status'] == 'assigned'])
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Farmer dashboard error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@app.route("/api/farmer/request/<int:request_id>/accept", methods=["POST"])
def farmer_accept_request(request_id):
    """Farmer accepts assignment request"""
    user = get_authenticated_user(request, 'farmer')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify request belongs to this farmer
        cur.execute("""
            SELECT ar.* FROM assignment_requests ar
            JOIN f_register f ON ar.farmer_id = f.f_id
            WHERE ar.assignment_request_id = %s AND f.user_id = %s AND ar.status = 'pending'
        """, (request_id, user['user_id']))
        
        req = cur.fetchone()
        
        if not req:
            return jsonify({"error": "Request not found"}), 404
        
        if req['expires_at'] < datetime.now():
            return jsonify({"error": "Request expired"}), 410
        
        # Accept request
        cur.execute("""
            UPDATE assignment_requests
            SET status = 'accepted', updated_at = NOW()
            WHERE assignment_request_id = %s
        """, (request_id,))
        
        # Create confirmed assignment
        cur.execute("""
            INSERT INTO confirmed_assignments (
                factory_id, farmer_id, machine_id, assigned_date,
                estimated_harvest_days, estimated_completion,
                production_kg, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'assigned')
        """, (
            req['factory_id'], req['farmer_id'], req['machine_id'],
            req['scheduled_date'], req['estimated_harvest_days'],
            req['estimated_completion'], req['production_kg']
        ))
        
        # Update machine status
        cur.execute("""
            UPDATE m_register SET m_status = 'busy'
            WHERE m_id = %s
        """, (req['machine_id'],))
        
        # Update crop status
        cur.execute("""
            UPDATE f_register SET status = 'assigned'
            WHERE f_id = %s
        """, (req['farmer_id'],))
        
        conn.commit()
        cur.close()
        
        logger.info(f" Request accepted: {request_id} by {user['name']}")
        
        return jsonify({"status": "success", "message": "Assignment accepted"}), 200
        
    except Exception as e:
        logger.error(f"Accept error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@app.route("/api/farmer/request/<int:request_id>/reject", methods=["POST"])
def farmer_reject_request(request_id):
    """Farmer rejects assignment request"""
    user = get_authenticated_user(request, 'farmer')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify and reject
        cur.execute("""
            UPDATE assignment_requests ar
            SET status = 'rejected', updated_at = NOW()
            FROM f_register f
            WHERE ar.assignment_request_id = %s 
            AND ar.farmer_id = f.f_id 
            AND f.user_id = %s 
            AND ar.status = 'pending'
            RETURNING ar.machine_id
        """, (request_id, user['user_id']))
        
        result = cur.fetchone()
        
        if not result:
            return jsonify({"error": "Request not found"}), 404
        
        # Release machine
        cur.execute("""
            UPDATE m_register SET m_status = 'idle'
            WHERE m_id = %s
        """, (result['machine_id'],))
        
        conn.commit()
        cur.close()
        
        logger.info(f"Request rejected: {request_id} by {user['name']}")
        
        return jsonify({"status": "success", "message": "Assignment rejected"}), 200
        
    except Exception as e:
        logger.error(f"Reject error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

# ==================== MACHINE OWNER ENDPOINTS ====================

@app.route("/api/machine/register", methods=["POST"])
def machine_owner_register_machine():
    """Machine owner registers a machine"""
    user = get_authenticated_user(request, 'machine_owner')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    required = ['address', 'district']
    
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO m_register (
                user_id, m_name, m_phone_number, m_factory, 
                m_address, m_district, m_status
            ) VALUES (%s, %s, %s, %s, %s, %s, 'idle')
            RETURNING m_id
        """, (
            user['user_id'], user['name'], user['phone'],
            user['factory_id'], data['address'], data['district']
        ))
        
        m_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        logger.info(f"✓ Machine registered: Owner {user['name']}")
        
        return jsonify({
            "status": "success",
            "m_id": m_id,
            "message": "Machine registered successfully"
        }), 201
        
    except Exception as e:
        logger.error(f"Machine registration error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@app.route("/api/machine/dashboard", methods=["GET"])
def machine_owner_dashboard():
    """Get machine owner dashboard"""
    user = get_authenticated_user(request, 'machine_owner')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get machines
        cur.execute("""
            SELECT * FROM m_register
            WHERE user_id = %s
            ORDER BY m_id DESC
        """, (user['user_id'],))
        machines = cur.fetchall()
        
        # Get assignments for user's machines
        cur.execute("""
            SELECT ca.*, f.f_name as farmer_name, f.f_phone_number as farmer_phone,
                   m.m_id
            FROM confirmed_assignments ca
            JOIN m_register m ON ca.machine_id = m.m_id
            JOIN f_register f ON ca.farmer_id = f.f_id
            WHERE m.user_id = %s
            ORDER BY ca.assigned_date DESC
            LIMIT 20
        """, (user['user_id'],))
        assignments = cur.fetchall()
        
        # Convert dates
        for item in machines + assignments:
            for k, v in item.items():
                if isinstance(v, (date, datetime)):
                    item[k] = v.isoformat()
        
        cur.close()
        
        return jsonify({
            "user": {
                "name": user['name'],
                "phone": user['phone'],
                "factory_id": user['factory_id']
            },
            "machines": machines,
            "assignments": assignments,
            "stats": {
                "total_machines": len(machines),
                "idle_machines": len([m for m in machines if m['m_status'] == 'idle']),
                "busy_machines": len([m for m in machines if m['m_status'] == 'busy']),
                "active_assignments": len([a for a in assignments if a['status'] == 'assigned'])
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Machine dashboard error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@app.route("/api/machine/<int:machine_id>/status", methods=["PUT"])
def update_machine_status(machine_id):
    """Machine owner updates machine status (busy to idle after harvest)"""
    user = get_authenticated_user(request, 'machine_owner')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    new_status = data.get('status')
    
    if new_status not in ['idle', 'busy']:
        return jsonify({"error": "Invalid status"}), 400
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify ownership
        cur.execute("""
            UPDATE m_register
            SET m_status = %s, updated_at = NOW()
            WHERE m_id = %s AND user_id = %s
            RETURNING m_id
        """, (new_status, machine_id, user['user_id']))
        
        result = cur.fetchone()
        
        if not result:
            return jsonify({"error": "Machine not found"}), 404
        
        # If changing to idle, mark assignment as completed
        if new_status == 'idle':
            cur.execute("""
                UPDATE confirmed_assignments
                SET status = 'completed', actual_completion_date = CURRENT_DATE
                WHERE machine_id = %s AND status = 'assigned'
            """, (machine_id,))
        
        conn.commit()
        cur.close()
        
        logger.info(f"✓ Machine {machine_id} status → {new_status}")
        
        return jsonify({
            "status": "success",
            "message": f"Machine status updated to {new_status}"
        }), 200
        
    except Exception as e:
        logger.error(f"Status update error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

# ==================== FACTORY ADMIN ENDPOINTS ====================

@app.route("/api/factory/dashboard", methods=["GET"])
def factory_dashboard():
    """Get factory dashboard with analytics"""
    user = get_authenticated_user(request, 'factory_admin')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        factory_id = user['factory_id']
        
        # Factory info
        cur.execute("SELECT * FROM factories WHERE factory_id = %s", (factory_id,))
        factory = cur.fetchone()
        
        # All farmers in this factory
        cur.execute("""
            SELECT f.*, u.name as user_name
            FROM f_register f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.f_factory = %s
            ORDER BY f.f_submission_date DESC
        """, (factory_id,))
        farmers = cur.fetchall()
        
        # All machines in this factory
        cur.execute("""
            SELECT m.*, u.name as owner_name
            FROM m_register m
            JOIN users u ON m.user_id = u.user_id
            WHERE m.m_factory = %s
            ORDER BY m.m_id DESC
        """, (factory_id,))
        machines = cur.fetchall()
        
        # Today's assignments
        cur.execute("""
            SELECT ca.*, 
                   f.f_name as farmer_name, f.f_crop,
                   m.m_name as machine_owner
            FROM confirmed_assignments ca
            JOIN f_register f ON ca.farmer_id = f.f_id
            JOIN m_register m ON ca.machine_id = m.m_id
            WHERE ca.factory_id = %s AND ca.assigned_date = CURRENT_DATE
            ORDER BY ca.assignment_id DESC
        """, (factory_id,))
        today_assignments = cur.fetchall()
        
        # Stats
        cur.execute("""
            SELECT 
                COUNT(*) as pending_farmers
            FROM f_register
            WHERE f_factory = %s AND status = 'pending'
        """, (factory_id,))
        pending_farmers = cur.fetchone()['pending_farmers']
        
        cur.execute("""
            SELECT 
                COALESCE(SUM(production_kg), 0) as today_production
            FROM confirmed_assignments
            WHERE factory_id = %s AND assigned_date = CURRENT_DATE
        """, (factory_id,))
        today_production = cur.fetchone()['today_production']
        
        idle_machines = len([m for m in machines if m['m_status'] == 'idle'])
        busy_machines = len([m for m in machines if m['m_status'] == 'busy'])
        
        # Chart data - last 7 days
        cur.execute("""
            SELECT 
                assigned_date,
                COUNT(*) as assignments,
                SUM(production_kg) as production
            FROM confirmed_assignments
            WHERE factory_id = %s 
            AND assigned_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY assigned_date
            ORDER BY assigned_date
        """, (factory_id,))
        chart_data = cur.fetchall()
        
        # Convert dates
        for item in farmers + machines + today_assignments + chart_data:
            for k, v in item.items():
                if isinstance(v, (date, datetime)):
                    item[k] = v.isoformat()
        
        cur.close()
        
        return jsonify({
            "factory": dict(factory),
            "farmers": farmers,
            "machines": machines,
            "today_assignments": today_assignments,
            "stats": {
                "total_farmers": len(farmers),
                "pending_farmers": pending_farmers,
                "total_machines": len(machines),
                "idle_machines": idle_machines,
                "busy_machines": busy_machines,
                "today_assignments": len(today_assignments),
                "today_production": float(today_production),
                "capacity": factory['daily_capacity'],
                "capacity_used_percent": (float(today_production) / factory['daily_capacity'] * 100) if factory['daily_capacity'] > 0 else 0
            },
            "chart_data": chart_data
        }), 200
        
    except Exception as e:
        logger.error(f"Factory dashboard error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@app.route("/api/factory/trigger-assignment", methods=["POST"])
def factory_trigger_assignment():
    """Factory admin manually triggers assignment job"""
    user = get_authenticated_user(request, 'factory_admin')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        from services.scheduler import schedule_harvesting_job
        schedule_harvesting_job()
        return jsonify({"status": "success", "message": "Assignment job completed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== NOTIFICATIONS ====================

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    """Get user notifications"""
    user = get_authenticated_user(request)
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM notifications
            WHERE user_id = %s
            ORDER BY sent_at DESC
            LIMIT 50
        """, (user['user_id'],))
        
        notifications = cur.fetchall()
        
        # Convert dates
        for notif in notifications:
            for k, v in notif.items():
                if isinstance(v, (date, datetime)):
                    notif[k] = v.isoformat()
        
        cur.close()
        
        return jsonify(notifications), 200
        
    except Exception as e:
        logger.error(f"Notifications error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

# Assignment scheduling is handled by backend/services/scheduler.py
# Use the scheduler implementation there. This file no longer contains the assignment logic.

# ==================== SCHEDULER ====================

# Use external scheduler implementation
from services.scheduler import start_scheduler as start_background_scheduler

# ==================== HEALTH CHECK ====================

@app.route("/api/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({"status": "ok", "time": datetime.now().isoformat()}), 200

# ==================== MAIN ====================

if os.getenv("FLASK_ENV") != "development":
    start_background_scheduler()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ["schedule", "run-scheduler", "assign"]:
            from services.scheduler import schedule_harvesting_job
            schedule_harvesting_job()
            sys.exit(0)
        if cmd in ["expire", "expire-requests"]:
            from services.scheduler import expire_pending_requests
            expire_pending_requests()
            sys.exit(0)

    logger.info("\n" + "="*70)
    logger.info("Sugarcane Harvesting System")
    logger.info("="*70)
    
    port = int(os.getenv("PORT", 5000))
    logger.info(f" Flask starting on http://0.0.0.0:{port}")
    logger.info("="*70 + "\n")
    
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)