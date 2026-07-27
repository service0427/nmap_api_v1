import requests
import os
import sys
import pymysql
from datetime import date

# Ensure core utils are accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import Config
from core.utils import get_kst_date

API_URL = "https://ghost2026.com/api/external/work"
DB_NAME = "ghost2026"

def get_default_work_amount():
    db_config = Config.get_db_config()
    site_db_config = db_config.copy()
    site_db_config['database'] = DB_NAME
    
    try:
        conn = pymysql.connect(**site_db_config)
        with conn.cursor() as cursor:
            cursor.execute("SELECT value FROM system_settings WHERE `key` = 'default_work_amount'")
            row = cursor.fetchone()
            if row and row.get('value'):
                return int(row['value'])
    except Exception:
        # Fallback to slot user
        try:
            fallback_config = site_db_config.copy()
            fallback_config['user'] = 'slot'
            fallback_config['password'] = 'Tech1324'
            conn = pymysql.connect(**fallback_config)
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM system_settings WHERE `key` = 'default_work_amount'")
                row = cursor.fetchone()
                if row and row.get('value'):
                    return int(row['value'])
        except Exception as e2:
            print(f"[GHOST2026] Failed to fetch default_work_amount from DB ({e2}). Falling back to 5.")
    return 5

def fetch_data():
    """
    GHOST2026 API로부터 데이터를 수집하여 표준 형식으로 반환.
    """
    try:
        kst_today = get_kst_date()
        kst_today_iso = kst_today.isoformat()
        kst_date_str = kst_today.strftime("%Y%m%d")
        
        url = f"{API_URL}?date={kst_today_iso}"
        print(f"[GHOST2026] Fetching data from: {url}")
        
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"[GHOST2026] HTTP Error: {resp.status_code}")
            return []
            
        res_data = resp.json()
        
        if isinstance(res_data, list):
            raw_items = res_data
        elif isinstance(res_data, dict):
            raw_items = res_data.get('items', [])
        else:
            print(f"[GHOST2026] Unexpected response type: {type(res_data)}")
            return []

        if not raw_items:
            print("[GHOST2026] API returned 0 items.")
            return []

        default_work_amount = get_default_work_amount()
        
        aggregated = {}
        for item in raw_items:
            code = str(item.get('code') or item.get('dest_id') or '').strip()
            if not code or code == 'None':
                continue
            try:
                work_amt = int(item.get('work_amount') or item.get('work_count') or default_work_amount)
            except (ValueError, TypeError):
                work_amt = default_work_amount
                
            search_keyword = item.get('keyword') or item.get('search_keyword') or ''
            start_date = item.get('start_date') or kst_today_iso
            end_date = item.get('expiry_date') or item.get('end_date') or kst_today_iso
            
            if code not in aggregated:
                aggregated[code] = {
                    'work_amount': work_amt,
                    'search_keyword': search_keyword,
                    'start_date': start_date,
                    'end_date': end_date
                }
            else:
                aggregated[code]['work_amount'] += work_amt

        standardized_data = []
        for index, (code, meta) in enumerate(aggregated.items()):
            slot_id = f"{kst_date_str}{index + 1:05d}"
            standardized_data.append({
                'sid': int(slot_id),
                'dest_id': code,
                'work_count': meta['work_amount'],
                'start_date': meta['start_date'],
                'end_date': meta['end_date'],
                'search_keyword': meta['search_keyword'],
                'target_url': f"https://m.place.naver.com/place/{code}"
            })
            
        print(f"[GHOST2026] Successfully processed {len(standardized_data)} slots.")
        return standardized_data

    except Exception as e:
        print(f"[GHOST2026] Fetch Exception: {e}")
        return []
