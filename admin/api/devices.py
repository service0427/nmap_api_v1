import os
import sys
from fastapi import APIRouter, HTTPException

# Path adjustment
ADMIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADMIN_DIR not in sys.path:
    sys.path.append(ADMIN_DIR)

from db import get_db_cursor
from core.utils import get_kst_now
from schemas import DeviceToggleMuteSchema, DeviceInfoUpdateSchema, DeviceGroupUpdateSchema

router = APIRouter()

@router.get("/api/v1/admin/history/device/{device_id}")
async def get_device_history(device_id: str):
    kst_now = get_kst_now()
    kst_date = kst_now.date()
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id as task_id, dest_id, dest_name, status, 
                       CONCAT(DATE_FORMAT(start_time, '%%H:%%i'), 
                              IF(end_time IS NULL, '<br/>~ 진행중', CONCAT('<br/>~ ', DATE_FORMAT(end_time, '%%H:%%i')))) as time,
                       TIMESTAMPDIFF(MINUTE, start_time, COALESCE(end_time, %s)) as duration
                FROM tasks_log 
                WHERE device_id = %s AND work_date = %s 
                ORDER BY start_time DESC
            """, (kst_now, device_id, kst_date))
            return cursor.fetchall()
    except Exception as e: 
        print(f"Admin API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/admin/device/toggle_mute")
async def toggle_device_mute(schema: DeviceToggleMuteSchema):
    device_id = schema.device_id
    is_muted = schema.is_muted
    try:
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE devices SET is_alert_muted = %s WHERE device_id = %s", (1 if is_muted else 0, device_id))
        return {"status": "ok", "device_id": device_id, "is_alert_muted": is_muted}
    except Exception as e:
        print(f"Admin API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/admin/device/info_update")
async def update_device_info(schema: DeviceInfoUpdateSchema):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                UPDATE devices 
                SET install_place = %s, install_count = %s, network_type = %s, hostname = %s
                WHERE device_id = %s
            """, (schema.install_place, schema.install_count, schema.network_type, schema.hostname, schema.device_id))
        return {"status": "ok"}
    except Exception as e:
        print(f"Admin API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/admin/device/group_update")
async def update_device_group_info(schema: DeviceGroupUpdateSchema):
    if not schema.device_ids:
        raise HTTPException(status_code=400, detail="device_ids list is required")
        
    try:
        with get_db_cursor() as cursor:
            format_strings = ','.join(['%s'] * len(schema.device_ids))
            query = f"""
                UPDATE devices 
                SET install_place = %s, install_count = %s, network_type = %s
                WHERE device_id IN ({format_strings})
            """
            params = [schema.install_place, schema.install_count, schema.network_type] + schema.device_ids
            cursor.execute(query, params)
        return {"status": "ok", "updated_count": len(schema.device_ids)}
    except Exception as e:
        print(f"Admin API Group Update Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/admin/device/reset_penalty")
async def reset_device_penalty_get(device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing device_id parameter")
    try:
        with get_db_cursor() as cursor:
            # 1. Reset penalty block time
            cursor.execute("UPDATE devices SET penalty_until = NULL WHERE device_id = %s", (device_id,))
            # 2. Reset today's failure stats so it doesn't get blocked again immediately on next failure
            kst_date = get_kst_now().date()
            cursor.execute("UPDATE device_daily_stats SET fail_cnt = 0 WHERE device_id = %s AND work_date = %s", (device_id, kst_date))
            print(f"[Admin API] Manually reset penalty and failures for device (GET): {device_id}")
        return {"status": "ok", "message": f"Penalty and failure count reset successfully for device {device_id}"}
    except Exception as e:
        print(f"Admin API Reset Penalty Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/admin/device/reset_penalty")
async def reset_device_penalty_post(data: dict):
    device_id = data.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing device_id in request body")
    try:
        with get_db_cursor() as cursor:
            # 1. Reset penalty block time
            cursor.execute("UPDATE devices SET penalty_until = NULL WHERE device_id = %s", (device_id,))
            # 2. Reset today's failure stats so it doesn't get blocked again immediately on next failure
            kst_date = get_kst_now().date()
            cursor.execute("UPDATE device_daily_stats SET fail_cnt = 0 WHERE device_id = %s AND work_date = %s", (device_id, kst_date))
            print(f"[Admin API] Manually reset penalty and failures for device (POST): {device_id}")
        return {"status": "ok", "message": f"Penalty and failure count reset successfully for device {device_id}"}
    except Exception as e:
        print(f"Admin API Reset Penalty Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/admin/device/reset_all_penalties")
async def reset_all_device_penalties_get():
    try:
        with get_db_cursor() as cursor:
            # 1. Reset penalty block time for all devices
            cursor.execute("UPDATE devices SET penalty_until = NULL")
            # 2. Reset today's failure stats for all devices
            kst_date = get_kst_now().date()
            cursor.execute("UPDATE device_daily_stats SET fail_cnt = 0 WHERE work_date = %s", (kst_date,))
            print("[Admin API] Manually reset penalty and failures for ALL devices (GET)")
        return {"status": "ok", "message": "All penalties and failure counts reset successfully"}
    except Exception as e:
        print(f"Admin API Reset All Penalties Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/v1/admin/device/reset_all_penalties")
async def reset_all_device_penalties_post():
    try:
        with get_db_cursor() as cursor:
            # 1. Reset penalty block time for all devices
            cursor.execute("UPDATE devices SET penalty_until = NULL")
            # 2. Reset today's failure stats for all devices
            kst_date = get_kst_now().date()
            cursor.execute("UPDATE device_daily_stats SET fail_cnt = 0 WHERE work_date = %s", (kst_date,))
            print("[Admin API] Manually reset penalty and failures for ALL devices (POST)")
        return {"status": "ok", "message": "All penalties and failure counts reset successfully"}
    except Exception as e:
        print(f"Admin API Reset All Penalties Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
