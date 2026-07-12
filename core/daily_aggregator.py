import os
import sys

# Path adjustment for standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from datetime import datetime, date, timedelta
from core.config import Config
from core.utils import get_kst_now, get_kst_date

# Config
DB_CONFIG = Config.get_fresh_db_config() if hasattr(Config, 'get_fresh_db_config') else Config.get_db_config()

def aggregate_daily_quota():
    """
    Initializes/Verifies today's and tomorrow's records in daily_progress.
    Inherits last_dist_m from previous successful day to enable long-term expansion.
    """
    kst_now = get_kst_now()
    kst_date = get_kst_date()
    print(f"--- Running Daily Aggregator: {kst_now} ---")
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            # Database Cleanup & Backup: Run once a day during the 3:00 AM hour KST to prevent bloat
            if kst_now.hour == 3:
                project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                cleanup_run_file = os.path.join(project_dir, "data/hashes/cleanup_last_run.txt")
                already_run = False
                if os.path.exists(cleanup_run_file):
                    with open(cleanup_run_file, "r") as f:
                        if f.read().strip() == kst_date.isoformat():
                            already_run = True
                            
                if not already_run:
                    print("  Running Database Cleanup...")
                    try:
                        # 7 days cleanup
                        cursor.execute("DELETE FROM tasks_log WHERE work_date < DATE_SUB(CURDATE(), INTERVAL 7 DAY)")
                        print(f"    Deleted old tasks_log: {cursor.rowcount} rows")
                        cursor.execute("DELETE FROM fail_log WHERE created_at < DATE_SUB(NOW(), INTERVAL 7 DAY)")
                        print(f"    Deleted old fail_log: {cursor.rowcount} rows")
                        cursor.execute("DELETE FROM allocation_failures WHERE kst_time < DATE_SUB(NOW(), INTERVAL 7 DAY)")
                        print(f"    Deleted old allocation_failures: {cursor.rowcount} rows")
                        cursor.execute("DELETE FROM optimizer_success_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL 7 DAY)")
                        print(f"    Deleted old optimizer_success_logs: {cursor.rowcount} rows")
                        
                        # 24 hours cleanup
                        cursor.execute("DELETE FROM ip_success_history WHERE last_success_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)")
                        print(f"    Deleted old ip_success_history: {cursor.rowcount} rows")
                        cursor.execute("DELETE FROM ip_allocation_history WHERE allocated_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)")
                        print(f"    Deleted old ip_allocation_history: {cursor.rowcount} rows")
                    except Exception as ex_clean:
                        print(f"    Error during database cleanup: {ex_clean}")
                    
                    # Daily Reset of Optimizer targets: Reset is_optimizer = 0 and restore default 3km ~ 15km range
                    print("  Running Daily Optimizer Reset...")
                    try:
                        cursor.execute("""
                            UPDATE places 
                            SET is_optimizer = 0,
                                dist_min_m = 3000,
                                dist_max_m = 15000,
                                check_status = 'NORMAL'
                            WHERE is_optimizer = 1 OR check_status = 'FAIL'
                        """)
                        print(f"    Reset {cursor.rowcount} places optimizer status and restored 3km~15km distances for the new day.")
                    except Exception as ex_reset:
                        print(f"    Error resetting daily optimizer places: {ex_reset}")
                    
                    # Daily Reset of Device penalties: Clear penalty_until to let failed devices retry on the new day
                    print("  Running Daily Device Penalty Reset...")
                    try:
                        cursor.execute("UPDATE devices SET penalty_until = NULL")
                        print(f"    Reset {cursor.rowcount} devices penalty status for the new day.")
                    except Exception as ex_dev_reset:
                        print(f"    Error resetting device penalties: {ex_dev_reset}")

                    # Automated daily database backup
                    print("  Running Automated Daily Database Backup...")
                    try:
                        from core.db_backup import run_backup
                        run_backup()
                    except Exception as ex_backup:
                        print(f"    Error during database backup: {ex_backup}")
                        
                    # Write completion file to prevent running again today
                    try:
                        os.makedirs(os.path.dirname(cleanup_run_file), exist_ok=True)
                        with open(cleanup_run_file, "w") as f:
                            f.write(kst_date.isoformat())
                    except Exception as ex_file:
                        print(f"    Error writing cleanup_last_run file: {ex_file}")
            # We initialize for both Today and Tomorrow to avoid the midnight gap
            days_to_sync = [kst_date, kst_date + timedelta(days=1)]
            
            for target_date in days_to_sync:
                d_str = target_date.isoformat()
                
                # Logic: Insert new record, or update if exists.
                # If inserting new: Try to fetch the most recent last_dist_m for this place.
                sql = """
                    INSERT INTO daily_progress (work_date, site_id, dest_id, sid, total_target, success_cnt, fail_cnt, last_dist_m, updated_at)
                    SELECT 
                        %s, 
                        s.site_id, 
                        s.dest_id, 
                        s.sid,
                        s.work_count,
                        0, 0,
                        IFNULL(
                            (SELECT dp2.last_dist_m FROM daily_progress dp2 
                             WHERE dp2.dest_id = s.dest_id 
                               AND dp2.work_date < %s 
                               AND dp2.success_cnt > 0
                             ORDER BY dp2.work_date DESC LIMIT 1), 
                            800
                        ),
                        %s
                    FROM raw_slots s
                    WHERE s.status = 'on'
                      AND s.is_deleted = 0
                      AND %s BETWEEN s.start_date AND s.end_date
                    ON DUPLICATE KEY UPDATE 
                        dest_id = VALUES(dest_id),
                        total_target = VALUES(total_target),
                        updated_at = %s;
                """
                # Parameters: target_date (for work_date), target_date (for subquery limit), kst_now (updated_at), target_date (for raw_slots filter), kst_now (on duplicate update)
                cursor.execute(sql, (d_str, d_str, kst_now, d_str, kst_now))
                print(f"  [{d_str}] Slots verified: {cursor.rowcount}")
            
        conn.commit()
    except Exception as e:
        print(f"Error in aggregator: {e}")
    finally:
        if 'conn' in locals(): conn.close()

def sync_workload_to_legacy():
    """
    Syncs local daily_progress (site_id = 'FSD') success_cnt and fail_cnt 
    back to the legacy FSD daily_tasks table.
    Disabled on nmap_api_v1 (100% independent server)
    """
    print("  [FSD] Legacy workload sync disabled on nmap_api_v1.")
    return

def calculate_7day_stats():
    """
    1) 과거 7일치(어제부터 과거 7일간)의 실제 수행 통계를 daily_progress로부터 daily_stats에 갱신.
    2) 오늘 포함 미래 7일치(D-0 ~ D+6)의 예상 슬롯 목표량을 raw_slots로부터 실시간 집계하여 daily_stats에 캐싱.
    """
    kst_now = get_kst_now()
    kst_date = get_kst_date()
    print(f"--- Calculating Rolling Stats (Past & Future): {kst_now} ---")
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            # 1. 과거 7일치 집계 (어제 D-1 ~ 7일전 D-7)
            past_sql = """
                INSERT INTO daily_stats (work_date, total_target, success_cnt, fail_cnt, updated_at)
                SELECT 
                    work_date,
                    SUM(total_target) as total_target,
                    SUM(success_cnt) as success_cnt,
                    SUM(fail_cnt) as fail_cnt,
                    %s
                FROM daily_progress
                WHERE work_date BETWEEN DATE_SUB(%s, INTERVAL 7 DAY) AND DATE_SUB(%s, INTERVAL 1 DAY)
                GROUP BY work_date
                ON DUPLICATE KEY UPDATE 
                    total_target = VALUES(total_target),
                    success_cnt = VALUES(success_cnt),
                    fail_cnt = VALUES(fail_cnt),
                    updated_at = VALUES(updated_at);
            """
            cursor.execute(past_sql, (kst_now, kst_date, kst_date))
            
            # 2. 오늘 포함 미래 7일치 집계 (오늘 D-0 ~ 6일후 D+6)
            for i in range(7):
                target_date = kst_date + timedelta(days=i)
                t_str = target_date.isoformat()
                
                # 해당 미래 날짜 기준 유효 슬롯들의 목표량 합산
                cursor.execute("""
                    SELECT SUM(work_count) as t_sum 
                    FROM raw_slots 
                    WHERE status = 'on' AND is_deleted = 0 
                      AND %s BETWEEN start_date AND end_date
                """, (t_str,))
                row = cursor.fetchone()
                target_sum = row['t_sum'] or 0

                # 오늘인 경우(D-0), 당일 실시간 성공/실패 수치도 함께 반영해 업서트
                if i == 0:
                    # places 상태별 카운트 집계
                    cursor.execute("""
                        SELECT 
                            SUM(CASE WHEN check_status = 'PENDING' THEN 1 ELSE 0 END) as p_cnt,
                            SUM(CASE WHEN check_status = 'VERIFIED' THEN 1 ELSE 0 END) as v_cnt,
                            SUM(CASE WHEN check_status = 'FAIL' THEN 1 ELSE 0 END) as f_cnt
                        FROM places
                    """)
                    places_stats = cursor.fetchone()
                    pending_places = places_stats['p_cnt'] or 0
                    verified_places = places_stats['v_cnt'] or 0
                    fail_places = places_stats['f_cnt'] or 0

                    cursor.execute("""
                        SELECT SUM(success_cnt) as s, SUM(fail_cnt) as f 
                        FROM daily_progress 
                        WHERE work_date = %s
                    """, (t_str,))
                    prog = cursor.fetchone()
                    s_cnt = prog['s'] or 0
                    f_cnt = prog['f'] or 0
                    
                    cursor.execute("""
                        INSERT INTO daily_stats (work_date, total_target, success_cnt, fail_cnt, pending_places, verified_places, fail_places, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            total_target = VALUES(total_target),
                            success_cnt = VALUES(success_cnt),
                            fail_cnt = VALUES(fail_cnt),
                            pending_places = VALUES(pending_places),
                            verified_places = VALUES(verified_places),
                            fail_places = VALUES(fail_places),
                            updated_at = VALUES(updated_at);
                    """, (t_str, target_sum, s_cnt, f_cnt, pending_places, verified_places, fail_places, kst_now))
                else:
                    # 미래 날짜들은 성공/실패가 0
                    cursor.execute("""
                        INSERT INTO daily_stats (work_date, total_target, success_cnt, fail_cnt, updated_at)
                        VALUES (%s, %s, 0, 0, %s)
                        ON DUPLICATE KEY UPDATE 
                            total_target = VALUES(total_target),
                            updated_at = VALUES(updated_at);
                    """, (t_str, target_sum, kst_now))
                    
            print(f"  Rolling stats (past & future) updated successfully.")
        conn.commit()
    except Exception as e:
        print(f"Error in calculate_7day_stats: {e}")
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    aggregate_daily_quota()
    sync_workload_to_legacy()
    calculate_7day_stats()
