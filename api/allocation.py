import random
import json
from datetime import timedelta
from typing import Optional, Union
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from core.config import Config

import api.helpers as helpers
from api.helpers import (
    get_db_cursor,
    allocation_lock,
    update_device_stats,
    log_allocation_failure,
    format_address,
    logger
)
from core.utils import (
    get_kst_now,
    get_kst_date,
    calculate_gps_and_speed,
    generate_spoofed_identity
)

router = APIRouter(tags=["Allocation"])

class TaskRequest(BaseModel):
    device_id: str
    ip: Optional[str] = "0.0.0.0"
    site_id: Optional[str] = None
    arrival_time: Optional[Union[int, str]] = None
    only_optimizer: Optional[bool] = False

@router.post("/api/v1/request_task")
async def request_task(req: TaskRequest, request: Request):
    # Increment metrics on shared helpers module
    helpers.request_counter += 1
    helpers.active_devices.add(req.device_id)
    
    kst_now, kst_date = get_kst_now(), get_kst_date()
    success_limit = Config.get_dest_success_limit()
    client_ip = req.ip if req.ip and req.ip != "0.0.0.0" and req.ip != "unknown" else None
    WORKING_LOCK_SEC = 900 # 15 Minutes to wait for client progress report
    
    try:
        with allocation_lock:
            with get_db_cursor() as cursor:
                update_device_stats(cursor, req.device_id)
                
                # 1. Device Verification
                cursor.execute("SELECT seq, device_id, status, orig_ssaid, orig_adid, orig_idfv, orig_ni, orig_token FROM devices WHERE device_id = %s AND status = 'on'", (req.device_id,))
                device_row = cursor.fetchone()
                if not device_row: 
                    log_allocation_failure(cursor, req.device_id, "UNAUTHORIZED_DEVICE", client_ip or "unknown", req.dict())
                    return {"status": "error", "msg": "UNAUTHORIZED_DEVICE"}

                # 2. Safety Exclusions (Strict 5-Minute Lock)
                cursor.execute("SELECT dest_id FROM tasks_log WHERE end_time IS NULL AND created_at > %s - INTERVAL %s SECOND", (kst_now, WORKING_LOCK_SEC))
                locked_dest_ids = {str(row['dest_id']) for row in cursor.fetchall()}

                # IP Exclusivity: Same IP cannot take same dest_id within the last 3 hours
                if client_ip:
                    three_hours_ago = kst_now - timedelta(hours=3)
                    cursor.execute("SELECT dest_id FROM ip_allocation_history WHERE ip = %s AND allocated_at >= %s", (client_ip, three_hours_ago))
                    ip_allocated_ids = {str(row['dest_id']) for row in cursor.fetchall()}
                else:
                    ip_allocated_ids = set()

                is_only_opt = bool(req.only_optimizer)
                if is_only_opt:
                    opt_condition = "AND p.is_optimizer = 1"
                    status_condition = "AND p.check_status IN ('VERIFIED', 'NORMAL', 'FAIL')"
                else:
                    opt_condition = "AND ((p.is_optimizer = 0 AND p.check_status IN ('VERIFIED', 'NORMAL')) OR (p.is_optimizer = 1 AND p.check_status IN ('VERIFIED', 'NORMAL', 'FAIL')))"
                    status_condition = ""
                
                base_query = f"""
                    SELECT 
                        dp.site_id, dp.sid, dp.dest_id, p.name, p.address, p.lat, p.lng, 
                        p.arr_min_s, p.arr_max_s, p.dist_min_m, p.dist_max_m, p.check_status, p.is_optimizer,
                        dp.total_target, dp.success_cnt as total_success,
                        (dp.total_target - dp.success_cnt) as remain_count,
                        dp.fail_cnt, dp.alloc_fail_cnt, dp.miss_cnt,
                        dp.last_dist_m,
                        r.search_keyword
                    FROM raw_slots r
                    JOIN daily_progress dp ON r.site_id = dp.site_id AND r.sid = dp.sid
                    JOIN places p ON r.dest_id = p.dest_id
                    WHERE dp.work_date = %s
                      AND %s BETWEEN r.start_date AND r.end_date
                      AND r.status = 'on'
                      AND r.is_deleted = 0
                      AND p.name NOT LIKE 'FAILED_SCRAPE_%%'
                      AND (
                          SELECT IFNULL(SUM(success_cnt), 0) 
                          FROM daily_progress 
                          WHERE dest_id = dp.dest_id AND work_date = dp.work_date
                      ) < {success_limit}
                      {status_condition}
                      {opt_condition}
                """
                params = [kst_date, kst_date]
                if req.site_id: 
                    base_query += " AND r.site_id = %s"
                    params.append(req.site_id)
                else: 
                    base_query += " AND r.site_id <> 'test'"
                
                base_query += """
                    AND (dp.total_target - dp.success_cnt) > 0 
                """
                cursor.execute(base_query, tuple(params))
                all_raw_candidates = cursor.fetchall()
                
                # Priority grouping
                group_zero = [] # Priority 1: 0 successes
                group_fail = [] # Priority 2: has failures (needs verify)
                group_rest = [] # Priority 3: rest
                
                for cand in all_raw_candidates:
                    dest_id = str(cand['dest_id'])
                    if dest_id in locked_dest_ids or dest_id in ip_allocated_ids: 
                        continue
                    
                    if cand['total_success'] == 0:
                        group_zero.append(cand)
                    elif cand['fail_cnt'] > 0:
                        group_fail.append(cand)
                    else:
                        group_rest.append(cand)

                # 3. Allocation decision with pool coordinate validation
                task = None
                pool_row = None
                candidate_lists = []
                
                if group_zero:
                    random.shuffle(group_zero)
                    candidate_lists.append(group_zero)
                
                if group_fail:
                    # Group by fail_cnt (descending) and shuffle each bucket to avoid patterns
                    fail_buckets = {}
                    for cand in group_fail:
                        fc = cand['fail_cnt']
                        fail_buckets.setdefault(fc, []).append(cand)
                    
                    sorted_fails = []
                    for fc in sorted(fail_buckets.keys(), reverse=True):
                        bucket = fail_buckets[fc]
                        random.shuffle(bucket)
                        sorted_fails.extend(bucket)
                    candidate_lists.append(sorted_fails)
                    
                if group_rest:
                    # Group by achievement rate (ascending in 10% buckets) and shuffle each bucket to avoid patterns
                    rate_buckets = {}
                    for cand in group_rest:
                        target = cand['total_target']
                        success = cand['total_success']
                        rate = success / target if target > 0 else 0
                        # Map to bucket index 0 to 9 (e.g. rate 0.25 -> bucket 2)
                        bucket_idx = min(9, int(rate * 10))
                        rate_buckets.setdefault(bucket_idx, []).append(cand)
                    
                    sorted_rests = []
                    for idx in sorted(rate_buckets.keys()):
                        bucket = rate_buckets[idx]
                        random.shuffle(bucket)
                        sorted_rests.extend(bucket)
                    candidate_lists.append(sorted_rests)

                for cand_list in candidate_lists:
                    for cand in cand_list:
                        if not cand['lat'] or not cand['lng']:
                            continue
                        
                        # miss_cnt > 2 이거나 is_optimizer = 1 인 경우 -> 무조건 검증된 풀(Pool)에서만 할당 가능
                        if cand.get('miss_cnt', 0) > 2 or bool(cand['is_optimizer']):
                            cursor.execute("""
                                SELECT id, lat, lng, dist_m, actual_rank 
                                FROM task_position_pool 
                                WHERE dest_id = %s AND created_date = %s AND is_used = 0
                                  AND (actual_rank BETWEEN 1 AND 8)
                                ORDER BY id ASC 
                                LIMIT 1
                            """, (cand['dest_id'], kst_date))
                            p_row = cursor.fetchone()
                            if p_row:
                                task = cand
                                pool_row = p_row
                                break
                            # 만약 풀에 검증된 좌표가 없다면, 할당하지 않고 다음 후보로 넘어감 (스킵)
                        else:
                            # Normal tasks are always valid (dynamic fallback calculation)
                            task = cand
                            break
                    if task:
                        break

                if not task:
                    # Excess Allocation Mode: Regular quotas are exhausted.
                    # Fall back to allocating from all active tasks today at random.
                    excess_query = f"""
                        SELECT 
                            dp.site_id, dp.sid, dp.dest_id, p.name, p.address, p.lat, p.lng, 
                            p.arr_min_s, p.arr_max_s, p.dist_min_m, p.dist_max_m, p.check_status, p.is_optimizer,
                            dp.total_target, dp.success_cnt as total_success,
                            dp.fail_cnt, dp.alloc_fail_cnt, dp.miss_cnt,
                            dp.last_dist_m,
                            r.search_keyword
                        FROM raw_slots r
                        JOIN daily_progress dp ON r.site_id = dp.site_id AND r.sid = dp.sid
                        JOIN places p ON r.dest_id = p.dest_id
                        WHERE dp.work_date = %s
                          AND %s BETWEEN r.start_date AND r.end_date
                          AND r.status = 'on'
                          AND r.is_deleted = 0
                          AND p.name NOT LIKE 'FAILED_SCRAPE_%%'
                          AND (
                              SELECT IFNULL(SUM(success_cnt), 0) 
                              FROM daily_progress 
                              WHERE dest_id = dp.dest_id AND work_date = dp.work_date
                          ) < {success_limit}
                          {status_condition}
                          {opt_condition}
                    """
                    params_ex = [kst_date, kst_date]
                    if req.site_id: 
                        excess_query += " AND r.site_id = %s"
                        params_ex.append(req.site_id)
                    else: 
                        excess_query += " AND r.site_id <> 'test'"

                    cursor.execute(excess_query, tuple(params_ex))
                    excess_candidates = cursor.fetchall()
                    
                    # Respect locks and IP limits even in excess mode
                    valid_excess = []
                    for cand in excess_candidates:
                        dest_id = str(cand['dest_id'])
                        if dest_id in locked_dest_ids or dest_id in ip_allocated_ids: 
                            continue
                        valid_excess.append(cand)
                    
                    if valid_excess:
                        # Shuffle completely to assign randomly
                        random.shuffle(valid_excess)
                        for cand in valid_excess:
                            if not cand['lat'] or not cand['lng']:
                                continue
                            
                            # miss_cnt > 2 이거나 is_optimizer = 1 인 경우 -> 무조건 검증된 풀(Pool)에서만 할당 가능
                            if cand.get('miss_cnt', 0) > 2 or bool(cand['is_optimizer']):
                                cursor.execute("""
                                    SELECT id, lat, lng, dist_m, actual_rank 
                                    FROM task_position_pool 
                                    WHERE dest_id = %s AND created_date = %s AND is_used = 0
                                      AND (actual_rank BETWEEN 1 AND 8)
                                    ORDER BY id ASC 
                                    LIMIT 1
                                """, (cand['dest_id'], kst_date))
                                p_row = cursor.fetchone()
                                if p_row:
                                    task = dict(cand)
                                    pool_row = p_row
                                    task['is_excess'] = True
                                    break
                            else:
                                task = dict(cand)
                                task['is_excess'] = True
                                break

                if not task:
                    log_allocation_failure(cursor, req.device_id, "NO_TASK_AVAILABLE", client_ip or "unknown", req.dict())
                    return {"status": "error", "msg": "NO_TASK_AVAILABLE"}

                # Record IP allocation for exclusivity check
                if client_ip:
                    cursor.execute("INSERT INTO ip_allocation_history (ip, dest_id, allocated_at) VALUES (%s, %s, %s)", (client_ip, task['dest_id'], kst_now))

                cursor.execute("SELECT keyword FROM place_keywords WHERE dest_id = %s AND status = 'on'", (task['dest_id'],))
                keywords = [row['keyword'] for row in cursor.fetchall()]
                if not keywords and task.get('search_keyword'):
                    keywords = [task['search_keyword']]
                if not keywords:
                    keywords = [task['name']]
                random.shuffle(keywords)
                
                final_arrival_s = req.arrival_time if req.arrival_time and int(req.arrival_time) > 0 else random.randint(int(task['arr_min_s']), int(task['arr_max_s']))
                if final_arrival_s < 300: 
                    final_arrival_s = 300

                final_lat, final_lng, final_dist, found_visible, search_keyword = 0.0, 0.0, 0.0, False, keywords[0]
                d_min_m = max(3000, int(task['dist_min_m']))
                d_max_m = min(15000, max(d_min_m, int(task['dist_max_m'])))

                if pool_row:
                    final_lat = float(pool_row['lat'])
                    final_lng = float(pool_row['lng'])
                    final_dist = float(pool_row['dist_m'])
                    # Mark it as used
                    cursor.execute("UPDATE task_position_pool SET is_used = 1 WHERE id = %s", (pool_row['id'],))
                    logger.info(f"[*] Pool-based Allocation for: {task['name']} (Using pool id {pool_row['id']}, dist: {final_dist}m)")
                else:
                    # Always dynamic calculation for normal tasks
                    final_lat, final_lng, final_dist, _ = calculate_gps_and_speed(float(task['lat']), float(task['lng']), d_min_m, d_max_m, 0, 0, fixed_arrival_s=final_arrival_s)
                    logger.info(f"[*] Dynamic Allocation for: {task['name']} (dist: {final_dist}m)")
                
                final_speed = round((final_dist / 1000.0) / (final_arrival_s / 3600.0), 2)
                if final_speed < 3.0:
                    final_arrival_s = max(60, int((final_dist / 1000.0) / 3.0 * 3600))
                    final_speed = 3.0
                elif final_speed > 80.0:
                    final_arrival_s = int((final_dist / 1000.0) / 80.0 * 3600)
                    final_speed = 80.0

                # 5. Identity Spoofing
                spoofed_id = generate_spoofed_identity()
                original_id = {"ssaid": device_row["orig_ssaid"], "adid": device_row["orig_adid"], "idfv": device_row["orig_idfv"], "ni": device_row["orig_ni"], "token": device_row["orig_token"]}

                task_sid = task['sid']
                checked_rank = pool_row['actual_rank'] if pool_row else None

                # 6. Final Insertion & Response
                msg_str = f"Start: {final_lat},{final_lng} | GoalTime: {final_arrival_s}s | Speed: {final_speed}km/h | Keyword: {search_keyword}"
                if task.get('is_excess'):
                    msg_str = "[EXCESS_ALLOCATION] " + msg_str
                    logger.info(f"[*] Excess-based Allocation for: {task['name']} (dist: {final_dist}m)")

                cursor.execute("""
                    INSERT INTO tasks_log (
                        work_date, site_id, sid, dest_id, dest_name, device_id, ip, spoofed_identity, 
                        status, result_msg, start_time, distance_m, start_lat, start_lng, checked_rank, 
                        speed_kmh, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'WORKING', %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    kst_date, task['site_id'], task_sid, task['dest_id'], task['name'], req.device_id, client_ip, json.dumps(spoofed_id), 
                    msg_str, kst_now, int(final_dist), final_lat, final_lng, checked_rank, 
                    final_speed, kst_now
                ))
                
                v1_task_id = cursor.connection.insert_id()


                
                return {
                    "status": "ok", 
                    "task_id": v1_task_id, 
                    "device_seq": device_row['seq'], 
                    "destination": {
                        "id": task['dest_id'], 
                        "target_name": task['name'], 
                        "search_keyword": search_keyword, 
                        "address": format_address(task['address']), 
                        "lat": float(task['lat']), 
                        "lng": float(task['lng'])
                    }, 
                    "start_pos": {
                        "lat": final_lat, 
                        "lng": final_lng, 
                        "speed_kmh": final_speed, 
                        "dist_m": final_dist
                    }, 
                    "arrival_time": final_arrival_s, 
                    "identity": {
                        "original": original_id, 
                        "spoofed": spoofed_id
                    }
                }
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {req.device_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
