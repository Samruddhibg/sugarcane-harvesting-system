from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
from psycopg.rows import dict_row
from db import get_db_conn, release_db_conn
from utils import verify_token, get_authenticated_user

common_bp = Blueprint('common', __name__)
logger = logging.getLogger(__name__)

@common_bp.route("/notifications", methods=["GET"])
def get_notifications():
    """Get user notifications"""
    user = get_authenticated_user(request)
    
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor(row_factory=dict_row)
        
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
                if isinstance(v, (datetime,)):
                    notif[k] = v.isoformat()
        
        cur.close()
        
        return jsonify(notifications), 200
        
    except Exception as e:
        logger.error(f"Notifications error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_conn(conn)

@common_bp.route("/health", methods=["GET"])
def health():
    """Health check"""
    return jsonify({"status": "ok", "time": datetime.now().isoformat()}), 200
