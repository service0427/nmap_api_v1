from datetime import timedelta
from typing import Optional, Union, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

import api.helpers as helpers
from api.helpers import (
    get_db_cursor,
    update_device_stats,
    update_device_ip,
    logger
)
from core.utils import get_kst_now, get_kst_date

router = APIRouter(tags=["Reporting"])

class ClientInfo(BaseModel):
    hostname: Optional[str] = None
    tailscale_ip: Optional[str] = None
    local_ip: Optional[str] = None
    public_ip: Optional[str] = None
    network_type: Optional[str] = None
    nmap_version: Optional[str] = None
    client_version: Optional[str] = None
    usb_slot: Optional[str] = None

class ResultReport(BaseModel):
    task_id: Optional[Union[int, str]] = None
    log_id: Optional[Union[int, str]] = None
    device_id: str
    status: str
    message: Optional[str] = None
    requested_address: Optional[str] = None
    actual_address: Optional[str] = None
    log_path: Optional[str] = None
    drive_dist: Optional[Any] = None
    drive_time: Optional[Any] = None
    calc_speed: Optional[Any] = None
    client_info: Optional[ClientInfo] = None
    has_429: Optional[bool] = False

class StatusUpdate(BaseModel):
    task_id: Optional[Union[int, str]] = None
    log_id: Optional[Union[int, str]] = None
    device_id: Optional[str] = None
    status: str
    drive_dist: Optional[Any] = None
    drive_time: Optional[Any] = None
    calc_speed: Optional[Any] = None
    real_ip: Optional[str] = None
    actual_address: Optional[str] = None
    requested_address: Optional[str] = None
    error_msg: Optional[str] = None
    log_path: Optional[str] = None
    client_info: Optional[ClientInfo] = None
    has_429: Optional[bool] = False

@router.post("/api/v1/report_result")
def report_result(report: ResultReport, request: Request):
    helpers.request_counter += 1
    actual_task_id = report.task_id or report.log_id
    logger.info(f"[*] /api/v1/report_result payload: task_id={report.task_id}, log_id={report.log_id}, device_id={report.device_id}, status={report.status}, message={report.message}, drive_dist={report.drive_dist}, drive_time={report.drive_time}")
    if not actual_task_id:
        return {"status": "REPORTED"}
        
    if report.status == 'FAIL' and report.message == 'INTERRUPTED_BY_NEW_TASK':
        report.status = 'CANCELED'

    kst_now, kst_date = get_kst_now().replace(tzinfo=None), get_kst_date()
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT status, site_id, sid, dest_id, distance_m, ip, device_id, client_dist_m, client_time_s, result_msg, start_lat, start_lng FROM tasks_log WHERE id = %s", (actual_task_id,))
            task_row = cursor.fetchone()
            if not task_row:
                logger.warning(f"[*] report_result: task ID {actual_task_id} not found in DB")
                return {"status": "REPORTED"}
            status_upper = (task_row['status'] or '').upper()
            logger.info(f"[*] report_result db check: task_id={actual_task_id}, db_status={status_upper}, db_device_id={task_row['device_id']}, db_client_dist={task_row['client_dist_m']}, db_client_time={task_row['client_time_s']}")
            
            def parse_int_metric(val):
                if val is None:
                    return 0
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    return 0

            client_dist = parse_int_metric(report.drive_dist)
            client_time = parse_int_metric(report.drive_time)
            client_speed = float(report.calc_speed) if report.calc_speed else 0.0
            
            logger.info(f"[*] report_result processing: status_upper={status_upper}, client_dist={client_dist}, client_time={client_time}, is_finished={status_upper in ['SUCCESS', 'FAIL'] or status_upper.startswith('FAIL')}")

            if status_upper in ['SUCCESS', 'FAIL'] or status_upper.startswith('FAIL'):
                # Even if already reported, if DB has under 50 for client metrics but incoming are >= 50, update them
                db_dist = task_row.get('client_dist_m') or 0
                db_time = task_row.get('client_time_s') or 0
                if db_dist < 50 or db_time < 50:
                    cursor.execute("""
                        UPDATE tasks_log 
                        SET client_dist_m = %s, client_time_s = %s, client_speed_kmh = %s, result_msg = %s 
                        WHERE id = %s
                    """, (client_dist, client_time, client_speed, report.message, actual_task_id))
                    
                # Revert FAIL_ZERO_DRIVE or FAIL to SUCCESS if we now have valid metrics
                if (status_upper == 'FAIL_ZERO_DRIVE' or status_upper == 'FAIL' or status_upper.startswith('FAIL')) and client_dist >= 50 and client_time >= 50:
                    cursor.execute("UPDATE tasks_log SET status = 'SUCCESS', end_time = %s WHERE id = %s", (kst_now, actual_task_id))
                    update_device_stats(cursor, report.device_id, success=1)
                    cursor.execute("DELETE FROM fail_log WHERE log_id = %s", (actual_task_id,))
                    cursor.execute("INSERT INTO ip_success_history (ip, dest_id, last_success_at) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE last_success_at = VALUES(last_success_at)", (task_row['ip'], task_row['dest_id'], kst_now))
                    cursor.execute("""
                        INSERT INTO daily_progress (work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, last_dist_m, last_success_at) 
                        VALUES (%s, %s, %s, %s, 1, 0, 0, %s, %s) 
                        ON DUPLICATE KEY UPDATE 
                            success_cnt=success_cnt+1, 
                            fail_cnt=GREATEST(0, fail_cnt-1), 
                            last_success_at=VALUES(last_success_at), 
                            miss_cnt=0,
                            last_dist_m=VALUES(last_dist_m)
                    """, (kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid'], task_row['distance_m'], kst_now))
                
                # Turn SUCCESS to FAIL_ZERO_DRIVE if metrics are under 50
                elif status_upper == 'SUCCESS' and (client_dist < 50 or client_time < 50):
                    new_msg = f"FAIL_ZERO_DRIVE: SUCCESS reported with dist={client_dist}, time={client_time} (original msg: {report.message})"
                    cursor.execute("UPDATE tasks_log SET status = 'FAIL_ZERO_DRIVE', result_msg = %s WHERE id = %s", (new_msg, actual_task_id))
                    update_device_stats(cursor, report.device_id, fail=1)
                    cursor.execute("""
                        INSERT INTO fail_log (log_id, device_id, dest_id, fail_status, error_msg)
                        VALUES (%s, %s, %s, 'FAIL_ZERO_DRIVE', %s)
                    """, (actual_task_id, report.device_id, task_row['dest_id'], new_msg))
                    cursor.execute("""
                        UPDATE daily_progress 
                        SET success_cnt = GREATEST(0, success_cnt - 1),
                            fail_cnt = fail_cnt + 1,
                            last_fail_at = %s
                        WHERE work_date = %s AND site_id = %s AND dest_id = %s AND sid = %s
                    """, (kst_now, kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid']))
                
                return {"status": "REPORTED"}

            orig_msg = task_row['result_msg'] or ""
            is_excess = orig_msg.startswith("[EXCESS_ALLOCATION]")
            final_report_msg = f"[EXCESS_ALLOCATION] {report.message or ''}" if is_excess else report.message

            val_has_429 = 1 if report.has_429 else 0
            if report.has_429:
                logger.warning(f"[*] HTTP 429 Detected for task {actual_task_id} (Device: {report.device_id}, IP: {task_row.get('ip') if task_row else 'unknown'})")

            cursor.execute("UPDATE tasks_log SET status = %s, result_msg = %s, end_time = %s, client_dist_m = %s, client_time_s = %s, client_speed_kmh = %s, has_429 = GREATEST(IFNULL(has_429, 0), %s) WHERE id = %s", (report.status, final_report_msg, kst_now, client_dist, client_time, client_speed, val_has_429, actual_task_id))
            
            if report.status == 'SUCCESS':
                if task_row['status'] != 'SUCCESS':
                    update_device_stats(cursor, report.device_id, success=1)
                    cursor.execute("INSERT INTO ip_success_history (ip, dest_id, last_success_at) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE last_success_at = VALUES(last_success_at)", (task_row['ip'], task_row['dest_id'], kst_now))
                    cursor.execute("INSERT INTO daily_progress (work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, last_dist_m, last_success_at) VALUES (%s, %s, %s, %s, 1, 0, 0, %s, %s) ON DUPLICATE KEY UPDATE success_cnt=success_cnt+1, last_success_at=VALUES(last_success_at), miss_cnt=0, last_dist_m=VALUES(last_dist_m)", (kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid'], task_row['distance_m'], kst_now))
            elif report.status == 'CANCELED':
                pass
            else:
                # Log to fail_log
                cursor.execute("""
                    INSERT INTO fail_log (log_id, device_id, dest_id, fail_status, requested_address, actual_address, error_msg, log_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (actual_task_id, report.device_id, task_row['dest_id'], report.status, report.requested_address, report.actual_address, report.message, report.log_path))

                is_error_log = False
                err_msg = (report.message or "").upper()
                status_str = (report.status or "").upper()
                if "ERROR_LOG_DETECTED" in err_msg or "ERROR_LOG_DETECTED" in status_str:
                    is_error_log = True

                if is_error_log and task_row and task_row.get('start_lat') and task_row.get('start_lng'):
                    cursor.execute("""
                        UPDATE task_position_pool 
                        SET is_used = 0 
                        WHERE dest_id = %s AND lat = %s AND lng = %s
                    """, (task_row['dest_id'], task_row['start_lat'], task_row['start_lng']))
                    logger.info(f"[*] ERROR_LOG_DETECTED: Reclaiming pool coordinate ({task_row['start_lat']}, {task_row['start_lng']}) for dest_id {task_row['dest_id']}")

                if not (task_row['status'] == 'FAIL' or task_row['status'].startswith('FAIL')):
                    status_str = str(report.status or "")
                    err_msg = str(report.message or "")
                    err_upper = err_msg.upper()
                    status_upper = status_str.upper()
                    
                    is_miss = False
                    if "ADDRESS_NOT_FOUND" in err_upper or "ADDRESS_NOT_FOUND" in status_upper:
                        is_miss = True
                    elif "목적지 검색 실패" in err_msg or "미노출" in err_msg or "검색 결과가 없습니다" in err_msg:
                        is_miss = True
                    elif "NOT_FOUND" in err_upper and "SEARCH_FIELD" not in err_upper and "GUIDANCE" not in err_upper:
                        is_miss = True
                    elif "MISS" in err_upper and "MISMATCH" not in err_upper:
                        is_miss = True

                    is_timeout = any(x in err_msg for x in ["TIMEOUT", "NETWORK", "타임아웃", "통신", "Network"])
                    is_mismatch = "IDENTITY_MISMATCH" in err_msg

                    val_miss = 1 if is_miss else 0
                    val_timeout = 1 if is_timeout else 0
                    val_mismatch = 1 if is_mismatch else 0

                    # A device should not experience a cooldown/penalty due to API-level or search exposure (is_miss) errors.
                    # Only increment the device's failure count if this is NOT a search visibility/miss error.
                    if not is_miss:
                        update_device_stats(cursor, report.device_id, fail=1)
                        
                        # Check if daily fail_cnt >= 60 to enforce 10-minute penalty block
                        cursor.execute("SELECT fail_cnt FROM device_daily_stats WHERE device_id = %s AND work_date = %s", (report.device_id, kst_date))
                        stat_row = cursor.fetchone()
                        if stat_row and stat_row.get('fail_cnt', 0) >= 60:
                            penalty_release = kst_now + timedelta(minutes=10)
                            cursor.execute("UPDATE devices SET penalty_until = %s WHERE device_id = %s", (penalty_release, report.device_id))
                            logger.warning(f"[PENALTY_ACTIVATED] Device {report.device_id} has exceeded 60 failures today. Blocked until {penalty_release}.")

                    cursor.execute("""
                        INSERT INTO daily_progress (
                            work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, 
                            miss_cnt, timeout_cnt, mismatch_cnt,
                            last_dist_m, last_fail_at
                        ) 
                        VALUES (%s, %s, %s, %s, 0, 1, 0, %s, %s, %s, %s, %s) 
                        ON DUPLICATE KEY UPDATE 
                            fail_cnt = fail_cnt + 1, 
                            miss_cnt = miss_cnt + VALUES(miss_cnt),
                            timeout_cnt = timeout_cnt + VALUES(timeout_cnt),
                            mismatch_cnt = mismatch_cnt + VALUES(mismatch_cnt),
                            last_fail_at = VALUES(last_fail_at)
                    """, (
                        kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid'], 
                        val_miss, val_timeout, val_mismatch, 
                        task_row['distance_m'], kst_now
                    ))
                    
                    # If miss_cnt >= 2, trigger re-verification, activate optimizer, and shrink distance without clearing details
                    cursor.execute("""
                        UPDATE places p
                        JOIN daily_progress dp ON p.dest_id = dp.dest_id
                        SET p.check_status = 'PENDING',
                            p.is_optimizer = 1,
                            p.dist_min_m = IF(p.dist_max_m > 3000, 1000, p.dist_min_m),
                            p.dist_max_m = IF(p.dist_max_m > 3000, 3000, p.dist_max_m),
                            p.last_checked_at = NULL
                        WHERE dp.dest_id = %s AND dp.work_date = %s AND dp.miss_cnt >= 2
                    """, (task_row['dest_id'], kst_date))
                    
                    # Purge pool coordinates exceeding new max distance
                    cursor.execute("""
                        DELETE FROM task_position_pool 
                        WHERE dest_id = %s 
                          AND dist_m > (SELECT dist_max_m FROM places WHERE dest_id = %s)
                    """, (task_row['dest_id'], task_row['dest_id']))
                    
                    logger.info(f"[*] Real-time Optimizer Activated for dest_id: {task_row['dest_id']} (miss_cnt >= 2)")
                    

            return {"status": "REPORTED"}
    except Exception as e: 
        logger.error(f"ERROR: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/api/v1/update_status")
def update_status(data: StatusUpdate, request: Request):
    helpers.request_counter += 1
    actual_task_id = data.task_id or data.log_id
    if not actual_task_id:
        return {"status": "UPDATED"}
        
    kst_now, kst_date = get_kst_now(), get_kst_date()
    
    def safe_int(val):
        if not val: return None
        try: return int(float(val))
        except: return None
        
    try:
        with get_db_cursor() as cursor:
            d_time = safe_int(data.drive_time)
            d_dist = safe_int(data.drive_dist)
            
            cursor.execute("SELECT status, site_id, sid, dest_id, distance_m, ip, device_id, client_dist_m, client_time_s, result_msg, start_lat, start_lng FROM tasks_log WHERE id = %s", (actual_task_id,))
            task_row = cursor.fetchone()

            # 1. Terminal State Protection: If the task is already finished, do not allow update_status to overwrite it
            if task_row:
                db_status = (task_row.get('status') or '').upper()
                if db_status in ['SUCCESS', 'FAIL', 'FAIL_ZERO_DRIVE', 'CANCELED'] or db_status.startswith('FAIL'):
                    return {"status": "REPORTED"}

            # Validation: SUCCESS must have drive_dist >= 50 and drive_time >= 50
            if data.status == 'SUCCESS':
                db_status = (task_row.get('status') or '').upper() if task_row else ''
                db_dist = task_row.get('client_dist_m') or 0 if task_row else 0
                db_time = task_row.get('client_time_s') or 0 if task_row else 0
                
                # Only perform FAIL_ZERO_DRIVE check if client actually sent metrics in this request
                if d_dist is not None and d_time is not None:
                    if db_status == 'SUCCESS' or (db_dist >= 50 and db_time >= 50):
                        pass
                    elif d_dist < 50 or d_time < 50:
                        data.status = 'FAIL_ZERO_DRIVE'
                        data.error_msg = f"FAIL_ZERO_DRIVE: SUCCESS reported with dist={d_dist}, time={d_time} (original msg: {data.error_msg or ''})"
            
            resolved_device_id = data.device_id or (task_row['device_id'] if task_row else None)
            if resolved_device_id:
                update_device_stats(cursor, resolved_device_id, duration=d_time if d_time else 0)
                if data.real_ip: 
                    update_device_ip(cursor, resolved_device_id, data.real_ip, kst_now)

                c_info = data.client_info
                if c_info:
                    dev_updates, dev_params = [], []
                    if c_info.hostname:
                        dev_updates.append("hostname = %s")
                        dev_params.append(c_info.hostname[:20])
                    if c_info.tailscale_ip:
                        dev_updates.append("tailscale_ip = %s")
                        dev_params.append(c_info.tailscale_ip[:45])
                    if c_info.local_ip:
                        dev_updates.append("local_ip = %s")
                        dev_params.append(c_info.local_ip[:45])
                    if c_info.network_type:
                        dev_updates.append("network_type = %s")
                        dev_params.append(c_info.network_type[:20])
                    if c_info.nmap_version:
                        dev_updates.append("nmap_version = %s")
                        dev_params.append(c_info.nmap_version[:20])
                    if c_info.client_version:
                        dev_updates.append("client_version = %s")
                        dev_params.append(c_info.client_version[:20])
                    if c_info.usb_slot:
                        dev_updates.append("usb_slot = %s")
                        dev_params.append(c_info.usb_slot[:20])
                    if dev_updates:
                        dev_params.append(resolved_device_id)
                        cursor.execute(f"UPDATE devices SET {', '.join(dev_updates)} WHERE device_id = %s", tuple(dev_params))

            # Record IP allocation for exclusivity check once we know the device's actual public IP
            if data.real_ip and data.real_ip != "Unknown" and task_row:
                if task_row.get('ip') != data.real_ip:
                    cursor.execute("INSERT INTO ip_allocation_history (ip, dest_id, allocated_at) VALUES (%s, %s, %s)", (data.real_ip, task_row['dest_id'], kst_now))
                
            status_is_fail = data.status == 'FAIL' or data.status.startswith('FAIL')
            db_status_is_fail = task_row and (task_row.get('status') == 'FAIL' or (task_row.get('status') or '').startswith('FAIL'))
            if status_is_fail and not db_status_is_fail:
                if resolved_device_id:
                    update_device_stats(cursor, resolved_device_id, fail=1)
                    cursor.execute("SELECT fail_cnt FROM device_daily_stats WHERE device_id = %s AND work_date = %s", (resolved_device_id, kst_date))
                    stat_row = cursor.fetchone()
                    if stat_row and stat_row.get('fail_cnt', 0) >= 60:
                        penalty_release = kst_now + timedelta(minutes=10)
                        cursor.execute("UPDATE devices SET penalty_until = %s WHERE device_id = %s", (penalty_release, resolved_device_id))
                if task_row:
                    cursor.execute("""
                        INSERT INTO daily_progress (
                            work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, 
                            last_dist_m, last_fail_at
                        ) 
                        VALUES (%s, %s, %s, %s, 0, 1, 0, %s, %s) 
                        ON DUPLICATE KEY UPDATE 
                            fail_cnt = fail_cnt + 1, 
                            last_fail_at = VALUES(last_fail_at)
                    """, (kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid'], task_row['distance_m'], kst_now))

            update_parts, params = ["status = %s"], [data.status]
            if data.status in ['SUCCESS', 'FAIL'] or data.status.startswith('FAIL'): 
                update_parts.append("end_time = %s")
                params.append(kst_now)
            if data.real_ip and data.real_ip != "Unknown": 
                update_parts.append("ip = %s")
                params.append(data.real_ip)
            if d_dist is not None: 
                update_parts.append("distance_m = %s")
                params.append(d_dist)
            if d_time is not None: 
                update_parts.append("duration_sec = %s")
                params.append(d_time)
                
            if data.has_429:
                update_parts.append("has_429 = 1")
                logger.warning(f"[*] HTTP 429 Detected in update_status for task {actual_task_id} (Device: {resolved_device_id})")

            status_str = data.status
            if data.actual_address or data.error_msg:
                status_str = f"{data.status} | Req:{data.requested_address} | Act:{data.actual_address} | Msg:{data.error_msg}"
                if data.status in ['SUCCESS', 'FAIL'] or data.status.startswith('FAIL'): 
                    update_parts.append("result_msg = %s")
                    params.append(status_str)
                    
            cursor.execute(f"UPDATE tasks_log SET {', '.join(update_parts)} WHERE id = %s", (*params, actual_task_id))
            

                
            if data.status in ['SUCCESS', 'FAIL'] or data.status.startswith('FAIL'):
                if task_row:
                    msg_for_legacy = data.error_msg if data.error_msg else data.status
                    if data.status == 'SUCCESS': 
                        if task_row['status'] != 'SUCCESS':
                            if data.device_id:
                                update_device_stats(cursor, data.device_id, success=1)
                            cursor.execute("INSERT INTO ip_success_history (ip, dest_id, last_success_at) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE last_success_at = VALUES(last_success_at)", (task_row['ip'], task_row['dest_id'], kst_now))
                            cursor.execute("INSERT INTO daily_progress (work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, last_dist_m, last_success_at) VALUES (%s, %s, %s, %s, 1, 0, 0, %s, %s) ON DUPLICATE KEY UPDATE success_cnt=success_cnt+1, last_success_at=VALUES(last_success_at), miss_cnt=0, last_dist_m=VALUES(last_dist_m)", (kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid'], task_row['distance_m'], kst_now))
                    else:
                        # Log to fail_log
                        dev_id = data.device_id or (task_row['device_id'] if task_row else None)
                        cursor.execute("""
                            INSERT INTO fail_log (log_id, device_id, dest_id, fail_status, requested_address, actual_address, error_msg, log_path)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (actual_task_id, dev_id, task_row['dest_id'] if task_row else "Unknown", data.status, data.requested_address, data.actual_address, data.error_msg, data.log_path))

                        is_error_log = False
                        err_msg = (data.error_msg or "").upper()
                        status_str = (data.status or "").upper()
                        if "ERROR_LOG_DETECTED" in err_msg or "ERROR_LOG_DETECTED" in status_str:
                            is_error_log = True

                        if is_error_log and task_row and task_row.get('start_lat') and task_row.get('start_lng'):
                            cursor.execute("""
                                UPDATE task_position_pool 
                                SET is_used = 0 
                                WHERE dest_id = %s AND lat = %s AND lng = %s
                            """, (task_row['dest_id'], task_row['start_lat'], task_row['start_lng']))
                            logger.info(f"[*] ERROR_LOG_DETECTED: Reclaiming pool coordinate ({task_row['start_lat']}, {task_row['start_lng']}) for dest_id {task_row['dest_id']}")

                        if not (task_row['status'] == 'FAIL' or task_row['status'].startswith('FAIL')):
                            if data.device_id:
                                update_device_stats(cursor, data.device_id, fail=1)
                                
                            status_str = str(data.status or "")
                            err_msg = str(data.error_msg or "")
                            is_miss = any(x in err_msg or x in status_str for x in ["NOT_FOUND", "MISS", "길찾기 결과가 없습니다", "미노출", "검색 실패", "목적지 검색 실패", "ADDRESS_NOT_FOUND"])
                            is_timeout = any(x in err_msg for x in ["TIMEOUT", "NETWORK", "타임아웃", "통신", "Network"])
                            is_mismatch = "IDENTITY_MISMATCH" in err_msg

                            val_miss = 1 if is_miss else 0
                            val_timeout = 1 if is_timeout else 0
                            val_mismatch = 1 if is_mismatch else 0

                            cursor.execute("""
                                INSERT INTO daily_progress (
                                    work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, 
                                    miss_cnt, timeout_cnt, mismatch_cnt,
                                    last_dist_m, last_fail_at
                                ) 
                                VALUES (%s, %s, %s, %s, 0, 1, 0, %s, %s, %s, %s, %s) 
                                ON DUPLICATE KEY UPDATE 
                                    fail_cnt = fail_cnt + 1, 
                                    miss_cnt = miss_cnt + VALUES(miss_cnt),
                                    timeout_cnt = timeout_cnt + VALUES(timeout_cnt),
                                    mismatch_cnt = mismatch_cnt + VALUES(mismatch_cnt),
                                    last_fail_at = VALUES(last_fail_at)
                            """, (
                                kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid'], 
                                val_miss, val_timeout, val_mismatch, 
                                task_row['distance_m'], kst_now
                            ))

                            # Immediately flag places.is_optimizer = 1 and shrink distance if miss_cnt >= 2
                            cursor.execute("""
                                UPDATE places p
                                JOIN daily_progress dp ON p.dest_id = dp.dest_id
                                SET p.is_optimizer = 1,
                                    p.dist_min_m = IF(p.dist_max_m > 3000, 1000, p.dist_min_m),
                                    p.dist_max_m = IF(p.dist_max_m > 3000, 3000, p.dist_max_m)
                                WHERE dp.dest_id = %s AND dp.work_date = %s AND dp.miss_cnt >= 2
                            """, (task_row['dest_id'], kst_date))

                            # Purge pool coordinates exceeding new max distance
                            cursor.execute("""
                                DELETE FROM task_position_pool 
                                WHERE dest_id = %s 
                                  AND dist_m > (SELECT dist_max_m FROM places WHERE dest_id = %s)
                            """, (task_row['dest_id'], task_row['dest_id']))

        return {"status": "UPDATED"}
    except Exception as e: 
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
