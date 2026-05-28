import os
import logging
from datetime import datetime, timedelta, date
from psycopg.rows import dict_row
from apscheduler.schedulers.background import BackgroundScheduler
from db import get_db_conn, release_db_conn
from utils import calculate_haversine_distance

logger = logging.getLogger(__name__)

# Configurable constants
MATURE_DAYS = 450
NEARLY_MATURE_DAYS = 400
# default per-machine acres/day when not provided in DB
DEFAULT_MACHINE_DAILY_CAPACITY = 50


def schedule_harvesting_job():
    """Run scheduling algorithm and create assignment requests for pending farmers."""
    logger.info("🔄 Running scheduling job...")

    conn = None
    try:
        conn = get_db_conn()
        if not conn:
            return
        cur = conn.cursor(row_factory=dict_row)

        # 1. Fetch pending farmers (pending status)
        cur.execute("""
            SELECT f.*, (CURRENT_DATE - f.f_planting_date) AS days_old, u.user_id AS farmer_user_id
            FROM f_register f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'pending'
            ORDER BY f.f_submission_date
        """)
        farmers = cur.fetchall()

        # 2. Fetch idle machines
        cur.execute("""
            SELECT m.*, u.user_id AS machine_user_id
            FROM m_register m
            JOIN users u ON m.user_id = u.user_id
            WHERE m_status = 'idle'
        """)
        machines = cur.fetchall()

        # Organize machines by factory for faster lookup
        machines_by_factory = {}
        for m in machines:
            machines_by_factory.setdefault(m['m_factory'], []).append(m)

        assignments_created = 0

        # 2. Prioritize farmers by age (days_old)
        for farmer in farmers:
            farmer_priority = int(farmer['days_old']) if farmer['days_old'] is not None else 0
            farmer['priority_score'] = farmer_priority

        farmers.sort(key=lambda x: x['priority_score'], reverse=True)

        # 3. Match farmers to machines
        for farmer in farmers:
            factory_id = farmer['f_factory']
            available_machines = machines_by_factory.get(factory_id, [])
            if not available_machines:
                continue

            best_machine = None
            min_cost = float('inf')

            for machine in available_machines:
                # district penalty
                district_penalty = 0 if machine.get('m_district') == farmer.get('f_district') else 50

                # approximate distance: use haversine if lat/lon present in columns, else fallback
                # we expect optional columns m_lat, m_lon, f_lat, f_lon; otherwise use 0/100 km heuristic
                try:
                    f_lat = farmer.get('f_lat')
                    f_lon = farmer.get('f_lon')
                    m_lat = machine.get('m_lat')
                    m_lon = machine.get('m_lon')
                    if f_lat is not None and f_lon is not None and m_lat is not None and m_lon is not None:
                        actual_dist = calculate_haversine_distance((f_lat, f_lon), (m_lat, m_lon))
                    else:
                        actual_dist = 0 if machine.get('m_district') == farmer.get('f_district') else 100
                except Exception:
                    actual_dist = 0 if machine.get('m_district') == farmer.get('f_district') else 100

                total_cost = actual_dist + district_penalty

                # machine capacity check
                machine_capacity = machine.get('m_daily_capacity') or DEFAULT_MACHINE_DAILY_CAPACITY
                farmer_acres = farmer.get('f_crop') or 0
                if machine_capacity >= farmer_acres and total_cost < min_cost:
                    min_cost = total_cost
                    best_machine = machine

            # 4. Create assignment request if matched
            if best_machine:
                est_days = max(1, int((farmer.get('f_crop') or 0) / (best_machine.get('m_daily_capacity') or DEFAULT_MACHINE_DAILY_CAPACITY)))
                try:
                    cur.execute("""
                        INSERT INTO assignment_requests (
                            factory_id, farmer_id, machine_id, scheduled_date,
                            estimated_harvest_days, estimated_completion,
                            production_kg, priority, status, request_sent_at, expires_at
                        ) VALUES (%s, %s, %s, CURRENT_DATE, %s, CURRENT_DATE + (%s || ' days')::interval, %s, %s, 'pending', NOW(), NOW() + INTERVAL '24 hours')
                        RETURNING assignment_request_id
                    """, (
                        factory_id,
                        farmer['f_id'],
                        best_machine['m_id'],
                        est_days,
                        est_days,
                        (farmer.get('f_crop') or 0) * 1000,
                        'mature' if farmer['priority_score'] >= MATURE_DAYS else ('nearly_mature' if farmer['priority_score'] >= NEARLY_MATURE_DAYS else 'normal')
                    ))

                    result = cur.fetchone()
                    if not result:
                        logger.error(f"INSERT returned no result for farmer {farmer.get('f_id')}")
                        continue
                    
                    ar_id = result['assignment_request_id']

                    # Reserve machine
                    cur.execute("""
                        UPDATE m_register SET m_status = 'reserved', updated_at = NOW()
                        WHERE m_id = %s
                    """, (best_machine['m_id'],))

                    # Notifications: farmer, machine owner, factory admins
                    cur.execute("""
                        INSERT INTO notifications (user_id, user_type, message) VALUES (%s, %s, %s)
                    """, (
                        farmer['farmer_user_id'], 'farmer', f'Assignment request #{ar_id} created. Machine {best_machine.get("m_name") or best_machine.get("m_id")}.'
                    ))

                    cur.execute("""
                        INSERT INTO notifications (user_id, user_type, message) VALUES (%s, %s, %s)
                    """, (
                        best_machine['machine_user_id'], 'machine_owner', f'Your machine {best_machine.get("m_name")} has a new assignment request #{ar_id}.'
                    ))

                    cur.execute("""
                        SELECT user_id FROM users WHERE role = 'factory_admin' AND factory_id = %s
                    """, (factory_id,))
                    admins = cur.fetchall()
                    for a in admins:
                        cur.execute("""
                            INSERT INTO notifications (user_id, user_type, message) VALUES (%s, %s, %s)
                        """, (a['user_id'], 'factory_admin', f'Assignment request #{ar_id} created for factory {factory_id}.'))

                    # Decrease local capacity counter, remove if exhausted
                    remaining_capacity = (best_machine.get('m_daily_capacity') or DEFAULT_MACHINE_DAILY_CAPACITY) - (farmer.get('f_crop') or 0)
                    best_machine['m_daily_capacity'] = remaining_capacity
                    if remaining_capacity <= 0:
                        machines_by_factory[factory_id].remove(best_machine)

                    assignments_created += 1
                except Exception as ex:
                    logger.error(f"Failed to create assignment for farmer {farmer.get('f_id')}: {ex}", exc_info=True)
                    continue

        conn.commit()
        cur.close()

        if assignments_created:
            logger.info(f"✅ Created {assignments_created} assignment requests")

    except Exception as e:
        logger.error(f"Scheduling job failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_conn(conn)


def expire_pending_requests():
    """Expire requests older than expiry and release machines; notify stakeholders."""
    conn = None
    try:
        conn = get_db_conn()
        if not conn:
            return
        cur = conn.cursor(row_factory=dict_row)

        cur.execute("""
            SELECT assignment_request_id, machine_id, farmer_id, factory_id
            FROM assignment_requests
            WHERE status = 'pending' AND expires_at < NOW()
        """)
        expired = cur.fetchall()

        for row in expired:
            cur.execute("""
                UPDATE assignment_requests SET status = 'expired', updated_at = NOW() WHERE assignment_request_id = %s
            """, (row['assignment_request_id'],))

            # release machine
            cur.execute("""
                UPDATE m_register SET m_status = 'idle', updated_at = NOW() WHERE m_id = %s
            """, (row['machine_id'],))

            # notify farmer, machine_owner, factory_admin
            cur.execute("""
                INSERT INTO notifications (user_id, user_type, message) VALUES (
                    (SELECT user_id FROM f_register fr JOIN users u ON fr.user_id = u.user_id WHERE fr.f_id = %s), 'farmer', %s
                )
            """, (row['farmer_id'], f'Assignment request #{row["assignment_request_id"]} expired'))

            cur.execute("""
                INSERT INTO notifications (user_id, user_type, message) VALUES (
                    (SELECT user_id FROM m_register mr JOIN users u ON mr.user_id = u.user_id WHERE mr.m_id = %s), 'machine_owner', %s
                )
            """, (row['machine_id'], f'Assignment request #{row["assignment_request_id"]} expired'))

            cur.execute("""
                SELECT user_id FROM users WHERE role = 'factory_admin' AND factory_id = %s
            """, (row['factory_id'],))
            admins = cur.fetchall()
            for a in admins:
                cur.execute("""
                    INSERT INTO notifications (user_id, user_type, message) VALUES (%s, %s, %s)
                """, (a['user_id'], 'factory_admin', f'Assignment request #{row["assignment_request_id"]} expired'))

        conn.commit()
        cur.close()
        if expired:
            logger.info(f"⏰ Expired {len(expired)} requests and released machines")

    except Exception as e:
        logger.error(f"Expiry job failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            release_db_conn(conn)


def start_scheduler():
    scheduler = BackgroundScheduler()

    # Run scheduling every 2 hours
    scheduler.add_job(schedule_harvesting_job, 'interval', hours=2, next_run_time=datetime.now() + timedelta(seconds=10))

    # Expire pending requests every 30 minutes
    scheduler.add_job(expire_pending_requests, 'interval', minutes=30, next_run_time=datetime.now() + timedelta(seconds=20))

    scheduler.start()
    logger.info("✓ Scheduler started (hourly scheduling, 30m expiry checks)")
