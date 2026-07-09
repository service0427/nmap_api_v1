import os
import psutil
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import api.helpers as helpers
from api.helpers import (
    get_db_cursor,
    update_device_ip,
    active_devices,
    logger
)
from core.utils import get_kst_now, get_kst_date
from core.config import Config

router = APIRouter(tags=["System"])

class LteUsageReport(BaseModel):
    name: str
    upload: int
    download: int
    ip: Optional[str] = None

@router.get("/api/v1/health")
def health_check():
    try:
        with get_db_cursor() as cursor: 
            cursor.execute("SELECT 1")
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        kst_now = get_kst_now()
        
        # Calculate uptime
        process_create_time = psutil.Process(os.getpid()).create_time()
        uptime_delta = kst_now - datetime.fromtimestamp(process_create_time, kst_now.tzinfo)
        uptime_str = str(uptime_delta).split('.')[0]
        
        return {
            "status": "healthy", 
            "kst_time": kst_now.strftime('%Y-%m-%d %H:%M:%S'), 
            "uptime": uptime_str, 
            "cpu": f"{psutil.cpu_percent()}%", 
            "ram_mb": round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2), 
            "disk": {
                "free_gb": round(disk.free / (1024**3), 2), 
                "total_gb": round(disk.total / (1024**3), 2), 
                "percent": f"{disk.percent}%"
            }, 
            "network_cumulative_mb": {
                "sent": round(net.bytes_sent / (1024 * 1024), 2), 
                "recv": round(net.bytes_recv / (1024 * 1024), 2)
            }, 
            "active_devices_now": len(active_devices), 
            "db": "connected"
        }
    except Exception as e: 
        return {"status": "unhealthy", "error": str(e)}

@router.get("/", response_class=HTMLResponse)
def dashboard():
    kst_now = get_kst_now()
    return f"<h1>Nmap Production API v1.1 Active</h1><p>KST: {kst_now.strftime('%Y-%m-%d %H:%M:%S')}</p><p><a href='/admin/'>Go to Admin Dashboard</a></p><p><a href='/api/v1/health'>Check Health Metrics</a></p>"

@router.post("/api/v1/lte_usage")
def report_lte_usage(report: LteUsageReport, request: Request):
    helpers.request_counter += 1
    kst_date = get_kst_date()
    kst_now = get_kst_now()
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT id FROM lte_data_usage WHERE modem_name = %s AND work_date = %s", (report.name, kst_date))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE lte_data_usage 
                    SET now_upload = %s, now_download = %s 
                    WHERE id = %s
                """, (report.upload, report.download, row['id']))
            else:
                cursor.execute("""
                    INSERT INTO lte_data_usage (modem_name, work_date, init_upload, init_download, now_upload, now_download) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (report.name, kst_date, report.upload, report.download, report.upload, report.download))
            
            # Update device current_ip if reported
            if report.ip:
                device_id = report.name.split('_')[0] if '_' in report.name else report.name
                update_device_ip(cursor, device_id, report.ip, kst_now)
        
        return {"status": "ok"}
    except Exception as e: 
        logger.error(f"LTE Usage Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
