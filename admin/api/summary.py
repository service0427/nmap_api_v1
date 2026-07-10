import os
import sys
import psutil
from datetime import timedelta
from fastapi import APIRouter
from fastapi.responses import JSONResponse

# Path adjustment
ADMIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADMIN_DIR not in sys.path:
    sys.path.append(ADMIN_DIR)

from db import get_db_cursor, check_is_deleted_support
from core.utils import get_kst_now, get_kst_date

router = APIRouter()

def get_stats_for_date(cursor, target_date, has_is_deleted):
    # 1. daily_progress 테이블 단독 집계로 속도 및 만료 유실 해결 (LUF, WJD 누락 방지)
    cursor.execute("""
        SELECT 
            site_id,
            SUM(IFNULL(total_target, 0)) as target,
            SUM(success_cnt) as success,
            SUM(fail_cnt) as fail
        FROM daily_progress
        WHERE work_date = %s
        GROUP BY site_id
    """, (target_date,))
    rows = cursor.fetchall()
    
    total_target_sum = sum(row['target'] for row in rows) if rows else 0
    if total_target_sum == 0:
        # Fallback: daily_progress가 아예 생성 전이거나 total_target이 없는 과거 레코드용 기존 쿼리
        is_deleted_filter1 = f"AND (rs.is_deleted = 0 OR (rs.is_deleted = 1 AND DATE(rs.deleted_at) >= '{target_date.isoformat()}'))" if has_is_deleted else ""
        cursor.execute(f"""
            SELECT 
                site_id,
                SUM(target) as target,
                SUM(success) as success,
                SUM(fail) as fail
            FROM (
                SELECT 
                    rs.site_id,
                    rs.work_count as target,
                    IFNULL(dp.success_cnt, 0) as success,
                    IFNULL(dp.fail_cnt, 0) as fail
                FROM raw_slots rs
                LEFT JOIN daily_progress dp ON rs.site_id = dp.site_id AND rs.sid = dp.sid AND dp.work_date = %s
                WHERE (rs.status = 'on' OR (rs.is_deleted = 1 AND DATE(rs.deleted_at) >= '{target_date.isoformat()}'))
                  {is_deleted_filter1}
                  AND %s BETWEEN rs.start_date AND rs.end_date
            ) t
            GROUP BY site_id
        """, (target_date, target_date))
        rows = cursor.fetchall()
        
    stats_by_site = {str(row['site_id']).upper(): row for row in rows}
    
    fsd = stats_by_site.get('FSD', {'target': 0, 'success': 0, 'fail': 0})
    luf = stats_by_site.get('LUF', {'target': 0, 'success': 0, 'fail': 0})
    ssolup = stats_by_site.get('SSOLUP', {'target': 0, 'success': 0, 'fail': 0})
    ghost2026 = stats_by_site.get('GHOST2026', {'target': 0, 'success': 0, 'fail': 0})
    rudolph = stats_by_site.get('RUDOLPH', {'target': 0, 'success': 0, 'fail': 0})
    quixslot = stats_by_site.get('QUIXSLOT', {'target': 0, 'success': 0, 'fail': 0})
    wjd = stats_by_site.get('WJDTJR07', {'target': 0, 'success': 0, 'fail': 0})
    if not wjd or (wjd.get('target', 0) == 0 and wjd.get('success', 0) == 0 and wjd.get('fail', 0) == 0):
        wjd = stats_by_site.get('WJDTJR', {'target': 0, 'success': 0, 'fail': 0})
    test = stats_by_site.get('TEST', {'target': 0, 'success': 0, 'fail': 0})
    
    fsd_target = fsd['target'] or 0
    fsd_success = fsd['success'] or 0
    fsd_fail = fsd['fail'] or 0
    
    luf_target = luf['target'] or 0
    luf_success = luf['success'] or 0
    luf_fail = luf['fail'] or 0
    
    ssolup_target = ssolup['target'] or 0
    ssolup_success = ssolup['success'] or 0
    ssolup_fail = ssolup['fail'] or 0
    
    ghost_target = ghost2026['target'] or 0
    ghost_success = ghost2026['success'] or 0
    ghost_fail = ghost2026['fail'] or 0
    
    rudolph_target = rudolph['target'] or 0
    rudolph_success = rudolph['success'] or 0
    rudolph_fail = rudolph['fail'] or 0
    
    quixslot_target = quixslot['target'] or 0
    quixslot_success = quixslot['success'] or 0
    quixslot_fail = quixslot['fail'] or 0
    
    wjd_target = wjd['target'] or 0
    wjd_success = wjd['success'] or 0
    wjd_fail = wjd['fail'] or 0
    
    test_target = test['target'] or 0
    test_success = test['success'] or 0
    test_fail = test['fail'] or 0
    
    total_active_target = luf_target + ssolup_target + ghost_target + rudolph_target + quixslot_target + wjd_target
    total_active_success = luf_success + ssolup_success + ghost_success + rudolph_success + quixslot_success + wjd_success
    total_active_fail = luf_fail + ssolup_fail + ghost_fail + rudolph_fail + quixslot_fail + wjd_fail
    
    return {
        "fsd_target": fsd_target,
        "fsd_success": fsd_success,
        "fsd_fail": fsd_fail,
        "luf_target": luf_target,
        "luf_success": luf_success,
        "luf_fail": luf_fail,
        "ssolup_target": ssolup_target,
        "ssolup_success": ssolup_success,
        "ssolup_fail": ssolup_fail,
        "ghost_target": ghost_target,
        "ghost_success": ghost_success,
        "ghost_fail": ghost_fail,
        "rudolph_target": rudolph_target,
        "rudolph_success": rudolph_success,
        "rudolph_fail": rudolph_fail,
        "quixslot_target": quixslot_target,
        "quixslot_success": quixslot_success,
        "quixslot_fail": quixslot_fail,
        "wjd_target": wjd_target,
        "wjd_success": wjd_success,
        "wjd_fail": wjd_fail,
        "test_target": test_target,
        "test_success": test_success,
        "test_fail": test_fail,
        "total_target": total_active_target,
        "success": total_active_success,
        "fail": total_active_fail,
        "remain": max(0, total_active_target - total_active_success)
    }

@router.get("/api/v1/admin/summary")
async def get_admin_summary(date: str = None):
    kst_now, kst_date = get_kst_now(), get_kst_date()
    query_date = kst_date
    if date:
        try:
            from datetime import datetime
            query_date = datetime.strptime(date, "%Y-%m-%d").date()
        except Exception:
            pass
    has_is_deleted = check_is_deleted_support()
    try:
        with get_db_cursor() as cursor:
            # 1. Task Summary Cards (yesterday, today, tomorrow)
            yesterday_stats = get_stats_for_date(cursor, kst_date - timedelta(days=1), has_is_deleted)
            today_stats = get_stats_for_date(cursor, kst_date, has_is_deleted)
            tomorrow_stats = get_stats_for_date(cursor, kst_date + timedelta(days=1), has_is_deleted)
            
            summary_stats = {
                "yesterday": yesterday_stats,
                "today": today_stats,
                "tomorrow": tomorrow_stats,
                "total_today_success": today_stats["success"],
                "total_yesterday_success": yesterday_stats["success"],
                "past_date_strs": [(kst_date - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
            }
            
            # 2. System Status
            disk = psutil.disk_usage('/')
            system_status = {
                "cpu": f"{psutil.cpu_percent()}%",
                "ram_mb": round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "kst_time": kst_now.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 3. Devices (Detailed - counting success/fail from tasks_log directly for real-time accuracy)
            cursor.execute("""
                SELECT d.device_id, d.current_ip, d.hostname, d.hostname as memo, d.status, d.is_alert_muted,
                       d.install_place, d.install_count, d.network_type,
                       DATE_FORMAT(d.penalty_until, '%%Y-%%m-%%d %%H:%%i:%%s') as penalty_until,
                       (SELECT dest_name FROM tasks_log WHERE device_id = d.device_id ORDER BY id DESC LIMIT 1) as current_dest,
                       (SELECT status FROM tasks_log WHERE device_id = d.device_id ORDER BY id DESC LIMIT 1) as current_status,
                       (SELECT result_msg FROM tasks_log WHERE device_id = d.device_id ORDER BY id DESC LIMIT 1) as last_result_msg,
                       (SELECT created_at FROM tasks_log WHERE device_id = d.device_id ORDER BY id DESC LIMIT 1) as last_task_at,
                       IFNULL(ds.success_cnt, 0) as today_success,
                       IFNULL(ds.fail_cnt, 0) as today_fail,
                       (SELECT end_time FROM tasks_log WHERE device_id = d.device_id AND status = 'SUCCESS' ORDER BY id DESC LIMIT 1) as last_success_at
                FROM devices d
                LEFT JOIN device_daily_stats ds ON d.device_id = ds.device_id AND ds.work_date = %s
                ORDER BY d.hostname ASC
            """, (kst_date,))
            devices_list = cursor.fetchall()

            # Pre-calculate silence levels for status warnings
            for d in devices_list:
                # Force status to uppercase for frontend compatibility
                d['status'] = (d['status'] or '').upper()
                d['silence_level'] = None
                d['silence_minutes'] = 0
                
                # Check for identity mismatch error
                d['has_identity_mismatch'] = False
                if d.get('last_result_msg') and 'IDENTITY_MISMATCH' in str(d['last_result_msg']):
                    d['has_identity_mismatch'] = True
                
                if d['status'] == 'ON':
                    # Warning triggers if last success is more than 20 minutes ago
                    last_success = d['last_success_at']
                    if last_success:
                        last_success_kst = last_success.replace(tzinfo=kst_now.tzinfo)
                        diff_seconds = (kst_now - last_success_kst).total_seconds()
                        diff_mins = int(diff_seconds // 60)
                        d['silence_minutes'] = diff_mins
                        if diff_seconds > 1200: # 20 minutes threshold
                            d['silence_level'] = 'danger'
                    else:
                        # Never had a successful task
                        d['silence_level'] = 'danger'
                        d['silence_minutes'] = 9999

            # 4. Destinations (Detailed - all slots for today including status)
            yesterday_date = query_date - timedelta(days=1)
            is_deleted_where_expr = "AND is_deleted = 0" if has_is_deleted else ""
            cursor.execute(f"""
                SELECT 
                    t.site_id,
                    t.dest_id,
                    p.name,
                    p.is_optimizer,
                    p.check_status,
                    p.dist_min_m,
                    p.dist_max_m,
                    p.max_total_limit,
                    p.max_active_slots,
                    t.start_date,
                    t.end_date,
                    t.target,
                    t.slot_status,
                    IFNULL(dp.success, 0) as success,
                    IFNULL(dp.fail, 0) as fail,
                    IFNULL(dp.miss, 0) as miss,
                    IFNULL(dp.timeout, 0) as timeout,
                    IFNULL(dp.mismatch, 0) as mismatch,
                    IFNULL(dp_y.success, 0) as y_success,
                    IFNULL(dp_y.fail, 0) as y_fail,
                    IF(la.dest_id IS NOT NULL, 1, 0) as is_adjusted
                FROM (
                    SELECT 
                        site_id,
                        dest_id,
                        MIN(start_date) as start_date,
                        MAX(end_date) as end_date,
                        SUM(work_count) as target,
                        MAX(status) as slot_status
                    FROM raw_slots
                    WHERE %s BETWEEN start_date AND end_date 
                      AND site_id <> 'test'
                      AND status = 'on'
                      {is_deleted_where_expr}
                    GROUP BY site_id, dest_id
                ) t
                JOIN places p ON t.dest_id = p.dest_id
                LEFT JOIN (
                    SELECT site_id, dest_id, 
                           SUM(success_cnt) as success, 
                           SUM(fail_cnt) as fail,
                           SUM(miss_cnt) as miss,
                           SUM(timeout_cnt) as timeout,
                           SUM(mismatch_cnt) as mismatch
                    FROM daily_progress
                    WHERE work_date = %s
                    GROUP BY site_id, dest_id
                ) dp ON t.site_id = dp.site_id AND t.dest_id = dp.dest_id
                LEFT JOIN (
                    SELECT site_id, dest_id, 
                           SUM(success_cnt) as success, 
                           SUM(fail_cnt) as fail
                    FROM daily_progress
                    WHERE work_date = %s
                    GROUP BY site_id, dest_id
                ) dp_y ON t.site_id = dp_y.site_id AND t.dest_id = dp_y.dest_id
                LEFT JOIN daily_limit_adjustments la ON t.dest_id = la.dest_id AND la.work_date = %s
                ORDER BY t.site_id ASC, t.dest_id ASC
            """, (query_date, query_date, yesterday_date, query_date))
            dest_list = cursor.fetchall()

            # 5. Live Alarms (Smart Anomaly Detection)
            alarms = []
            for d in devices_list:
                if d.get('is_alert_muted'):
                    continue
                # 1) Failure count alert
                if d['today_fail'] >= 5 and d['today_fail'] > d['today_success']:
                    alarms.append({
                        "type": "DEVICE", 
                        "level": "danger", 
                        "target": d['hostname'] or d['device_id'], 
                        "msg": f"실패 과다 (성공 {d['today_success']}회 | 실패 {d['today_fail']}회)"
                    })
                # 2) Silence alert using calculated level
                elif d['silence_level']:
                    msg = "마지막 통신 없음"
                    if d['last_task_at']:
                        msg = f"{d['silence_minutes']}분 전 통신"
                    alarms.append({
                        "type": "DEVICE", 
                        "level": d['silence_level'], 
                        "target": d['hostname'] or d['device_id'], 
                        "msg": msg
                    })
            
            # 6. Recent Successes (Last 50 with Memo)
            cursor.execute("""
                SELECT l.dest_name, IFNULL(d.hostname, l.device_id) as device_memo, l.start_time, l.end_time, 
                       IFNULL(NULLIF(l.client_time_s, 0), TIMESTAMPDIFF(SECOND, l.start_time, l.end_time)) as duration_sec 
                FROM tasks_log l
                LEFT JOIN devices d ON l.device_id = d.device_id
                WHERE l.status='SUCCESS' 
                ORDER BY l.id DESC LIMIT 50
            """)
            recent_successes = cursor.fetchall()

            # 8. LTE Usage (Join with yesterday's data for comparison)
            yesterday_date = kst_date - timedelta(days=1)
            cursor.execute("""
                SELECT 
                    t.modem_name,
                    t.init_upload as today_init_up,
                    t.init_download as today_init_dn,
                    t.now_upload as today_now_up,
                    t.now_download as today_now_dn,
                    t.updated_at as today_updated_at,
                    y.init_upload as yesterday_init_up,
                    y.init_download as yesterday_init_dn,
                    y.now_upload as yesterday_now_up,
                    y.now_download as yesterday_now_dn
                FROM lte_data_usage t
                LEFT JOIN lte_data_usage y ON t.modem_name = y.modem_name AND y.work_date = %s
                WHERE t.work_date = %s
                ORDER BY t.modem_name ASC
            """, (yesterday_date, kst_date))
            lte_usage = cursor.fetchall()

            # 9. Device History & Efficiency (Past 7 Days Success Accumulation)
            past_dates = [kst_date - timedelta(days=i) for i in range(7)]
            past_dates.reverse()  # Oldest to newest (index 6 is today)
            past_date_strs = [d.strftime('%Y-%m-%d') for d in past_dates]
            yesterday_str = yesterday_date.strftime('%Y-%m-%d')
            today_str = kst_date.strftime('%Y-%m-%d')

            cursor.execute("""
                SELECT device_id, work_date, success_cnt
                FROM device_daily_stats
                WHERE work_date >= %s
            """, (past_dates[0],))
            history_rows = cursor.fetchall()

            device_history_map = {}
            for row in history_rows:
                dev_id = row['device_id']
                w_date = row['work_date'].strftime('%Y-%m-%d')
                s_cnt = row['success_cnt'] or 0
                if dev_id not in device_history_map:
                    device_history_map[dev_id] = {}
                device_history_map[dev_id][w_date] = s_cnt

            total_today_success = 0
            total_yesterday_success = 0

            for d in devices_list:
                dev_id = d['device_id']
                history_list = []
                for dt_str in past_date_strs:
                    if dt_str == today_str:
                        val = d['today_success']
                    else:
                        val = device_history_map.get(dev_id, {}).get(dt_str, 0)
                    history_list.append(val)
                d['history_success'] = history_list
                d['yesterday_success'] = device_history_map.get(dev_id, {}).get(yesterday_str, 0)
                total_today_success += d['today_success']
                total_yesterday_success += device_history_map.get(dev_id, {}).get(yesterday_str, 0)

            summary_stats["total_today_success"] = total_today_success
            summary_stats["total_yesterday_success"] = total_yesterday_success
            summary_stats["past_date_strs"] = past_date_strs
            
        return {
            "summary": summary_stats,
            "system": system_status, 
            "devices": devices_list, 
            "destinations": dest_list, 
            "logs": [], 
            "lte": lte_usage, 
            "alarms": alarms[:20],
            "success_feed": recent_successes
        }
    except Exception as e:
        print(f"Admin API Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
