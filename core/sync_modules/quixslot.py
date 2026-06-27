import requests
import os
import sys
import pymysql
from datetime import date

# Ensure core utils are accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import Config
from core.utils import get_kst_date

API_URL = "https://quixslot.com/api/external/work-details"
DB_NAME = "quixslot_dev"

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
            print(f"[QUIXSLOT] Failed to fetch default_work_amount from DB ({e2}). Falling back to 5.")
    return 5

def fetch_data():
    """
    QUIXSLOT API로부터 데이터를 수집하여 표준 형식으로 반환.
    """
    try:
        kst_today = get_kst_date()
        kst_today_iso = kst_today.isoformat()
        
        all_items = []
        page = 1
        limit = 1000
        default_work_amount = get_default_work_amount()
        
        while True:
            url = f"{API_URL}?date={kst_today_iso}&page={page}&limit={limit}"
            print(f"[QUIXSLOT] Fetching page {page} from {url}...")
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"[QUIXSLOT] HTTP Error: {resp.status_code}")
                break
                
            data = resp.json()
            items = data.get('items', [])
            if not items:
                break
                
            all_items.extend(items)
            print(f"[QUIXSLOT] Page {page}: Got {len(items)} items. Total: {len(all_items)}")
            
            total = data.get('total', 0)
            if len(all_items) >= total or len(items) < limit:
                break
            page += 1
            
        if not all_items:
            return []
            
        standardized_data = []
        for item in all_items:
            sid = item.get('slot_id') or item.get('sid')
            dest_id = item.get('code')
            if not sid or not dest_id:
                continue
            
            start_date = item.get('start_date') or kst_today_iso
            end_date = item.get('expiry_date') or item.get('end_date') or kst_today_iso
            search_keyword = item.get('keyword') or ''
            
            standardized_data.append({
                'sid': int(sid),
                'dest_id': str(dest_id).strip(),
                'work_count': default_work_amount,
                'start_date': start_date,
                'end_date': end_date,
                'search_keyword': search_keyword,
                'target_url': f"https://m.place.naver.com/place/{dest_id}"
            })
            
        return standardized_data
    except Exception as e:
        print(f"[QUIXSLOT] Fetch Exception: {e}")
        return None
