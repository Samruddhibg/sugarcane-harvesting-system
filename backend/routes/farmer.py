from flask import Blueprint, request, jsonify
import logging
from datetime import date, datetime
from psycopg.rows import dict_row
from db import get_db_conn, release_db_conn
from utils import verify_token, get_authenticated_user

farmer_bp = Blueprint('farmer', __name__)
logger = logging.getLogger(__name__)

@farmer_bp.route("/register-crop", methods=["POST"])
def register_crop():
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
        
        logger.info(f"✓ Crop registered: Farmer {user['name']} - {data['crop_acres']} acres")
        
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

@farmer_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Get farmer dashboard data"""
    user = get_authenticated_user(request, 'farmer')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(row_factory=dict_row)
        
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

@farmer_bp.route("/request/<int:request_id>/accept", methods=["POST"])
def accept_request(request_id):
    """Farmer accepts assignment request"""
    user = get_authenticated_user(request, 'farmer')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(row_factory=dict_row)
        
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

        # Cleanup: remove other pending requests for same farmer
        cur.execute("""
            UPDATE assignment_requests SET status = 'cancelled', updated_at = NOW()
            WHERE farmer_id = %s AND status = 'pending' AND assignment_request_id != %s
        """, (req['farmer_id'], request_id))

        # Notify machine owner and factory admins
        cur.execute("""
            INSERT INTO notifications (user_id, user_type, message) VALUES (
                (SELECT user_id FROM m_register WHERE m_id = %s), 'machine_owner', %s
            )
        """, (req['machine_id'], f'Farmer accepted assignment #{request_id}.'))

        cur.execute("""
            SELECT user_id FROM users WHERE role = 'factory_admin' AND factory_id = %s
        """, (req['factory_id'],))
        admins = cur.fetchall()
        for a in admins:
            cur.execute("""
                INSERT INTO notifications (user_id, user_type, message) VALUES (%s, %s, %s)
            """, (a['user_id'], 'factory_admin', f'Farmer accepted assignment #{request_id}.'))
        
        conn.commit()
        cur.close()
        
        logger.info(f"✓ Request accepted: {request_id} by {user['name']}")
        
        return jsonify({"status": "success", "message": "Assignment accepted"}), 200
        
    except Exception as e:
        logger.error(f"Accept error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@farmer_bp.route("/request/<int:request_id>/reject", methods=["POST"])
def reject_request(request_id):
    """Farmer rejects assignment request"""
    user = get_authenticated_user(request, 'farmer')
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(row_factory=dict_row)
        
        # Verify and reject
        cur.execute("""
            UPDATE assignment_requests ar
            SET status = 'rejected', updated_at = NOW()
            FROM f_register f
            WHERE ar.assignment_request_id = %s 
            AND ar.farmer_id = f.f_id 
            AND f.user_id = %s 
            AND ar.status = 'pending'
            RETURNING ar.machine_id, ar.farmer_id, ar.factory_id
        """, (request_id, user['user_id']))
        
        result = cur.fetchone()
        
        if not result:
            return jsonify({"error": "Request not found"}), 404
        
        # Release machine
        cur.execute("""
            UPDATE m_register SET m_status = 'idle'
            WHERE m_id = %s
        """, (result['machine_id'],))

        # Notify machine owner and factory admins
        cur.execute("""
            INSERT INTO notifications (user_id, user_type, message) VALUES (
                (SELECT user_id FROM m_register WHERE m_id = %s), 'machine_owner', %s
            )
        """, (result['machine_id'], f'Farmer rejected assignment #{request_id}.'))

        cur.execute("""
            SELECT user_id FROM users WHERE role = 'factory_admin' AND factory_id = %s
        """, (result['factory_id'],))
        admins = cur.fetchall()
        for a in admins:
            cur.execute("""
                INSERT INTO notifications (user_id, user_type, message) VALUES (%s, %s, %s)
            """, (a['user_id'], 'factory_admin', f'Farmer rejected assignment #{request_id}.'))
        
        conn.commit()
        cur.close()
        
        logger.info(f"✓ Request rejected: {request_id} by {user['name']}")
        
        return jsonify({"status": "success", "message": "Assignment rejected"}), 200
        
    except Exception as e:
        logger.error(f"Reject error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)
