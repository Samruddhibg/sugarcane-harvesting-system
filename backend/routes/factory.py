from flask import Blueprint, request, jsonify
import logging
from datetime import date, datetime
from psycopg.rows import dict_row
from db import get_db_conn, release_db_conn
from utils import verify_token

factory_bp = Blueprint('factory', __name__)
logger = logging.getLogger(__name__)

@factory_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """Get factory dashboard with analytics"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    
    if not user or user['role'] != 'factory_admin':
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(row_factory=dict_row)
        
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

@factory_bp.route("/trigger-assignment", methods=["POST"])
def trigger_assignment():
    """Factory admin manually triggers assignment job"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user = verify_token(token)
    
    if not user or user['role'] != 'factory_admin':
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        from services.scheduler import daily_assignment_job
        daily_assignment_job()
        return jsonify({"status": "success", "message": "Assignment job completed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
