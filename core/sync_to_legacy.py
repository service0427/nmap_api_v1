import pymysql
import sys
import os
from datetime import datetime

# Path adjustment
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)

from core.config import Config
from core.utils import get_kst_now, get_kst_date

def sync_to_legacy():
    print("=== Starting Batch Sync to Legacy Server (Local -> Old) ===")
    
    local_conf = Config.get_db_config()
    local_conf['database'] = 'nmap_api'
    
    legacy_conf = Config.get_source_fsd_config()
    if not legacy_conf.get('host'):
        print("[Sync-Legacy] Skip: Source DB configuration is missing.")
        return
        
    try:
        local_conn = pymysql.connect(**local_conf)
        legacy_conn = pymysql.connect(**legacy_conf, autocommit=True)
        
        kst_date = get_kst_date()
        
        # 1. Sync Device IPs
        print("[1/2] Syncing Device IPs...")
        kst_now = get_kst_now()
        with local_conn.cursor(pymysql.cursors.DictCursor) as loc_cur:
            loc_cur.execute("SELECT device_id, current_ip, ip_updated_at FROM devices WHERE current_ip IS NOT NULL AND ip_updated_at >= %s - INTERVAL 10 MINUTE", (kst_now,))
            active_devs = loc_cur.fetchall()
            
        if active_devs:
            with legacy_conn.cursor() as leg_cur:
                for dev in active_devs:
                    leg_cur.execute("""
                        UPDATE devices 
                        SET current_ip = %s, ip_updated_at = %s 
                        WHERE device_id = %s
                    """, (dev['current_ip'], dev['ip_updated_at'], dev['device_id']))
            print(f"      - Synced {len(active_devs)} active device IPs.")
        else:
            print("      - No recent device IP updates to sync.")
            
        # 2. Sync Unsynced Tasks
        print("[2/2] Syncing Task Logs...")
        with local_conn.cursor(pymysql.cursors.DictCursor) as loc_cur:
            # Fetch unsynced logs (legacy_synced = 0)
            loc_cur.execute("""
                SELECT id, work_date, site_id, sid, dest_id, dest_name, device_id, ip,
                       distance_m, duration_sec, start_time, end_time, status,
                       legacy_task_id
                FROM tasks_log 
                WHERE legacy_synced = 0
                ORDER BY id ASC
                LIMIT 500
            """)
            unsynced_tasks = loc_cur.fetchall()
            
        if unsynced_tasks:
            synced_count = 0
            with legacy_conn.cursor() as leg_cur:
                for task in unsynced_tasks:
                    is_final = task['status'] in ['SUCCESS', 'FAIL'] or task['status'].startswith('FAIL')
                    
                    if not task['legacy_task_id']:
                        # Case A: New Task Log to insert
                        leg_cur.execute("""
                            INSERT INTO task_log (device_id, dest_id, dest_name, ip, status, start_time, distance_m, duration_sec, end_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            task['device_id'], task['dest_id'], task['dest_name'], task['ip'],
                            task['status'], task['start_time'], task['distance_m'], 
                            task['duration_sec'] or 0, task['end_time']
                        ))
                        legacy_id = leg_cur.lastrowid
                        
                        # Sync daily_tasks allocation timestamp to legacy
                        leg_cur.execute("""
                            INSERT INTO daily_tasks (dest_id, work_date, last_assigned_at)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE last_assigned_at = VALUES(last_assigned_at)
                        """, (task['dest_id'], task['work_date'] or kst_date, task['start_time']))
                        
                        # Update local row with legacy task ID
                        with local_conn.cursor() as loc_cur:
                            loc_cur.execute("UPDATE tasks_log SET legacy_task_id = %s WHERE id = %s", (legacy_id, task['id']))
                            
                        # If already completed at creation, mark synced and update legacy daily_tasks
                        if is_final:
                            with local_conn.cursor() as loc_cur:
                                loc_cur.execute("UPDATE tasks_log SET legacy_synced = 1 WHERE id = %s", (task['id'],))
                            if task['status'] == 'SUCCESS' and task['site_id'] != 'test':
                                leg_cur.execute("""
                                    INSERT INTO daily_tasks (dest_id, work_date, success_count, fail_count, last_success_at)
                                    VALUES (%s, %s, 1, 0, %s)
                                    ON DUPLICATE KEY UPDATE success_count = success_count + 1, fail_count = 0, last_success_at = VALUES(last_success_at)
                                """, (task['dest_id'], task['work_date'] or kst_date, task['end_time']))
                                
                    else:
                        # Case B: Update Existing Task Log
                        leg_cur.execute("""
                            UPDATE task_log 
                            SET status = %s, ip = %s, distance_m = %s, duration_sec = %s, end_time = %s
                            WHERE id = %s
                        """, (
                            task['status'], task['ip'], task['distance_m'], 
                            task['duration_sec'] or 0, task['end_time'],
                            task['legacy_task_id']
                        ))
                        
                        if is_final:
                            with local_conn.cursor() as loc_cur:
                                loc_cur.execute("UPDATE tasks_log SET legacy_synced = 1 WHERE id = %s", (task['id'],))
                            if task['status'] == 'SUCCESS' and task['site_id'] != 'test':
                                leg_cur.execute("""
                                    INSERT INTO daily_tasks (dest_id, work_date, success_count, fail_count, last_success_at)
                                    VALUES (%s, %s, 1, 0, %s)
                                    ON DUPLICATE KEY UPDATE success_count = success_count + 1, fail_count = 0, last_success_at = VALUES(last_success_at)
                                """, (task['dest_id'], task['work_date'] or kst_date, task['end_time']))
                                
                    synced_count += 1
            local_conn.commit()
            print(f"      - Synced {synced_count} task logs.")
        else:
            print("      - No unsynced task logs.")
            
        local_conn.close()
        legacy_conn.close()
        print("=== Legacy Sync Complete ===")
        
    except Exception as e:
        print(f"[Sync-Legacy Error] {e}")

if __name__ == "__main__":
    sync_to_legacy()
