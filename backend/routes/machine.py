from flask import Blueprint, request, jsonify
import logging
from datetime import date, datetime
from psycopg.rows import dict_row
from db import get_db_conn, release_db_conn
from utils import verify_token, get_authenticated_user

machine_bp = Blueprint('machine', __name__)
logger = logging.getLogger(__name__)

@machine_bp.route("/register", methods=["POST"])
def register_machine():
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

@machine_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Get machine owner dashboard"""
    user = get_authenticated_user(request, 'machine_owner')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(row_factory=dict_row)
        
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

@machine_bp.route("/<int:machine_id>/status", methods=["PUT"])
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
        cur = conn.cursor(row_factory=dict_row)
        
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
