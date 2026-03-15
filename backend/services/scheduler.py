import os
import logging
from datetime import datetime, timedelta
from psycopg.rows import dict_row
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_db_conn, release_db_conn

logger = logging.getLogger(__name__)

MATURITY_DAYS = 450
NEARLY_MATURE_DAYS = 400
FACTORY_IDS = list(range(1, 8))

def daily_assignment_job():
    """Main assignment job - simplified version"""
    logger.info("🔄 Running assignment job...")
    
    conn = None
    try:
        conn = get_db_conn()
        if not conn:
            return
        cur = conn.cursor(row_factory=dict_row)
        
        # Get pending farmers
        cur.execute("""
            SELECT f.*, (CURRENT_DATE - f.f_planting_date) as days_old
            FROM f_register f
            WHERE f.status = 'pending'
            ORDER BY f.f_submission_date
        """)
        farmers = cur.fetchall()
        
        # Get idle machines
        cur.execute("""
            SELECT * FROM m_register
            WHERE m_status = 'idle'
        """)
        machines = cur.fetchall()
        
        # Group by factory
        machines_by_factory = {}
        for m in machines:
            if m['m_factory'] not in machines_by_factory:
                machines_by_factory[m['m_factory']] = []
            machines_by_factory[m['m_factory']].append(m)
        
        assigned_count = 0
        
        # Assign mature farmers first
        for farmer in farmers:
            if farmer['days_old'] >= MATURITY_DAYS:
                factory_id = farmer['f_factory']
                if factory_id in machines_by_factory and machines_by_factory[factory_id]:
                    machine = machines_by_factory[factory_id].pop(0)
                    
                    # Create assignment request
                    cur.execute("""
                        INSERT INTO assignment_requests (
                            factory_id, farmer_id, machine_id, scheduled_date,
                            estimated_harvest_days, estimated_completion,
                            production_kg, priority, status, request_sent_at, expires_at
                        ) VALUES (%s, %s, %s, CURRENT_DATE, 5, CURRENT_DATE + 5, %s, 'mature', 'pending', NOW(), NOW() + INTERVAL '12 hours')
                    """, (factory_id, farmer['f_id'], machine['m_id'], farmer['f_crop'] * 1000))
                    
                    # Reserve machine
                    cur.execute("""
                        UPDATE m_register SET m_status = 'reserved'
                        WHERE m_id = %s
                    """, (machine['m_id'],))
                    
                    assigned_count += 1
        
        conn.commit()
        cur.close()
        
        logger.info(f"✅ Assignment job complete: {assigned_count} assignments created")
        
    except Exception as e:
        logger.error(f"❌ Assignment job failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_conn(conn)

def check_expired_requests():
    """Check and expire old requests"""
    conn = None
    try:
        conn = get_db_conn()
        if not conn:
            return
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE assignment_requests
            SET status = 'expired'
            WHERE status = 'pending' AND expires_at < NOW()
            RETURNING machine_id
        """)
        
        expired = cur.fetchall()
        
        for row in expired:
            cur.execute("""
                UPDATE m_register SET m_status = 'idle'
                WHERE m_id = %s
            """, (row[0],))
        
        conn.commit()
        cur.close()
        
        if expired:
            logger.info(f"⏰ Expired {len(expired)} requests")
        
    except Exception as e:
        logger.error(f"Expiry check error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_conn(conn)

def start_scheduler():
    """Start background jobs"""
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(daily_assignment_job, 'interval', hours=24, 
                      next_run_time=datetime.now() + timedelta(seconds=30))
    
    scheduler.add_job(check_expired_requests, 'interval', hours=1,
                      next_run_time=datetime.now() + timedelta(minutes=5))
    
    scheduler.start()
    logger.info("✓ Scheduler started")
