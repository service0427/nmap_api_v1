import pymysql
import re
import json
import logging
import sys
import threading
import psutil
from typing import Set, Optional, Any
from contextlib import contextmanager

from dbutils.pooled_db import PooledDB
from core.config import Config
from core.utils import get_kst_now, get_kst_date, generate_spoofed_identity, calculate_gps_and_speed
from core.scraper import NaverPlaceScraper

# Configure logging for v1_1
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("nmap_api_v1_1")

# --- Global Connection Pool ---
db_pool = PooledDB(
    creator=pymysql,
    mincached=5,
    maxcached=20,
    maxconnections=50,
    blocking=True,
    **Config.get_db_config()
)

@contextmanager
def get_db_cursor():
    """Fetches a connection from the global pool and provides a cursor."""
    conn = db_pool.connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

scraper_instance = NaverPlaceScraper()
allocation_lock = threading.Lock()

# --- Monitoring State ---
request_counter = 0
active_devices: Set[str] = set()

# --- Helper Functions ---
def update_device_stats(cursor, device_id, success=0, fail=0, alloc_fail=0, duration=0):
    kst_now, kst_date = get_kst_now(), get_kst_date()
    sql = """
        INSERT INTO device_daily_stats (device_id, work_date, success_cnt, fail_cnt, alloc_fail_cnt, total_duration_sec, last_active_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            success_cnt = success_cnt + VALUES(success_cnt),
            fail_cnt = fail_cnt + VALUES(fail_cnt),
            alloc_fail_cnt = alloc_fail_cnt + VALUES(alloc_fail_cnt),
            total_duration_sec = total_duration_sec + VALUES(total_duration_sec),
            last_active_at = VALUES(last_active_at)
    """
    cursor.execute(sql, (device_id, kst_date, success, fail, alloc_fail, duration, kst_now))

def update_device_ip(cursor, device_id: str, new_ip: str, kst_now):
    if not device_id or not new_ip:
        return False
    
    new_ip = new_ip.strip()
    if new_ip.lower() in ("unknown", "none", "null", "undefined", "127.0.0.1", "localhost"):
        return False
    
    ipv4_pattern = re.compile(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')
    is_valid = False
    if ipv4_pattern.match(new_ip):
        parts = new_ip.split('.')
        try:
            if all(0 <= int(part) <= 255 for part in parts):
                is_valid = True
        except ValueError:
            pass
    elif ":" in new_ip and 3 <= len(new_ip) <= 45:
        is_valid = True
        
    if not is_valid:
        return False
        
    cursor.execute("SELECT current_ip FROM devices WHERE device_id = %s", (device_id,))
    row = cursor.fetchone()
    if not row:
        return False
        
    prev_ip = row.get('current_ip')
    prev_ip_norm = prev_ip.strip() if prev_ip else None
    
    if prev_ip_norm != new_ip:
        cursor.execute("UPDATE devices SET current_ip = %s, ip_updated_at = %s WHERE device_id = %s", (new_ip, kst_now, device_id))
        cursor.execute(
            "INSERT INTO device_ip_rotation_logs (device_id, prev_ip, new_ip, changed_at) VALUES (%s, %s, %s, %s)",
            (device_id, prev_ip, new_ip, kst_now)
        )
        return True
    return False

def log_allocation_failure(cursor, device_id, error_msg, ip, payload=None):
    kst_now = get_kst_now()
    cursor.execute("INSERT INTO allocation_failures (device_id, error_msg, kst_time, ip, payload) VALUES (%s, %s, %s, %s, %s)", 
                   (device_id, error_msg, kst_now, ip, json.dumps(payload) if payload else None))

def format_address(addr: Optional[str]) -> Optional[str]:
    import re
    if not addr: return addr
    parts = addr.strip().split(' ')
    if len(parts) <= 1:
        return addr.strip()
    clean_parts = parts[1:]
    cutoff_index = len(clean_parts)
    for idx, part in enumerate(clean_parts):
        if re.match(r'^\d+(-\d+)?$', part):
            cutoff_index = idx + 1
            break
    return ' '.join(clean_parts[:cutoff_index]).strip()
