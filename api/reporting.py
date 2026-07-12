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

@router.post("/api/v1/report_result")
def report_result(report: ResultReport, request: Request):
    helpers.request_counter += 1
    actual_task_id = report.task_id or report.log_id
    if not actual_task_id:
        return {"status": "REPORTED"}
        
    kst_now, kst_date = get_kst_now().replace(tzinfo=None), get_kst_date()
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT status, site_id, sid, dest_id, distance_m, ip, device_id, result_msg FROM tasks_log WHERE id = %s", (actual_task_id,))
            task_row = cursor.fetchone()
            if not task_row:
                return {"status": "REPORTED"}
            status_upper = (task_row['status'] or '').upper()
            if status_upper in ['SUCCESS', 'FAIL'] or status_upper.startswith('FAIL'): 
                return {"status": "REPORTED"}
            
            client_dist = int(report.drive_dist) if report.drive_dist and str(report.drive_dist).isdigit() else 0
            client_time = int(report.drive_time) if report.drive_time and str(report.drive_time).isdigit() else 0
            client_speed = float(report.calc_speed) if report.calc_speed else 0.0

            orig_msg = task_row['result_msg'] or ""
            is_excess = orig_msg.startswith("[EXCESS_ALLOCATION]")
            final_report_msg = f"[EXCESS_ALLOCATION] {report.message or ''}" if is_excess else report.message

            cursor.execute("UPDATE tasks_log SET status = %s, result_msg = %s, end_time = %s, client_dist_m = %s, client_time_s = %s, client_speed_kmh = %s WHERE id = %s", (report.status, final_report_msg, kst_now, client_dist, client_time, client_speed, actual_task_id))
            
            if report.status == 'SUCCESS':
                if task_row['status'] != 'SUCCESS':
                    update_device_stats(cursor, report.device_id, success=1)
                    cursor.execute("INSERT INTO ip_success_history (ip, dest_id, last_success_at) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE last_success_at = VALUES(last_success_at)", (task_row['ip'], task_row['dest_id'], kst_now))
                    cursor.execute("INSERT INTO daily_progress (work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, last_dist_m, last_success_at) VALUES (%s, %s, %s, %s, 1, 0, 0, %s, %s) ON DUPLICATE KEY UPDATE success_cnt=success_cnt+1, last_success_at=VALUES(last_success_at), miss_cnt=0, last_dist_m=VALUES(last_dist_m)", (kst_date, task_row['site_id'], task_row['dest_id'], task_row['sid'], task_row['distance_m'], kst_now))

            else:
                # Log to fail_log
                cursor.execute("""
                    INSERT INTO fail_log (log_id, device_id, dest_id, fail_status, requested_address, actual_address, error_msg, log_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (actual_task_id, report.device_id, task_row['dest_id'], report.status, report.requested_address, report.actual_address, report.message, report.log_path))

                if not (task_row['status'] == 'FAIL' or task_row['status'].startswith('FAIL')):
                    update_device_stats(cursor, report.device_id, fail=1)
                    
                    # Check if daily fail_cnt >= 60 to enforce 10-minute penalty block
                    cursor.execute("SELECT fail_cnt FROM device_daily_stats WHERE device_id = %s AND work_date = %s", (report.device_id, kst_date))
                    stat_row = cursor.fetchone()
                    if stat_row and stat_row.get('fail_cnt', 0) >= 60:
                        penalty_release = kst_now + timedelta(minutes=10)
                        cursor.execute("UPDATE devices SET penalty_until = %s WHERE device_id = %s", (penalty_release, report.device_id))
                        logger.warning(f"[PENALTY_ACTIVATED] Device {report.device_id} has exceeded 60 failures today. Blocked until {penalty_release}.")
                    
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
            
            cursor.execute("SELECT status, site_id, sid, dest_id, distance_m, ip, device_id, result_msg FROM tasks_log WHERE id = %s", (actual_task_id,))
            task_row = cursor.fetchone()
            
            if data.device_id:
                update_device_stats(cursor, data.device_id, duration=d_time if d_time else 0)
                if data.real_ip: 
                    update_device_ip(cursor, data.device_id, data.real_ip, kst_now)

            # Record IP allocation for exclusivity check once we know the device's actual public IP
            if data.real_ip and data.real_ip != "Unknown" and task_row:
                if task_row.get('ip') != data.real_ip:
                    cursor.execute("INSERT INTO ip_allocation_history (ip, dest_id, allocated_at) VALUES (%s, %s, %s)", (data.real_ip, task_row['dest_id'], kst_now))
                
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
