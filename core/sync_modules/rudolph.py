import requests
import time
import os
import sys
import re
from datetime import date

# Ensure core utils are accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.utils import get_kst_date

def extract_place_id(url):
    if not url:
        return None
    url = str(url).strip()
    match = re.search(r'/(?:place|restaurant|hospital|hairshop|nail|accommodation|stay|hotel|camping|resort|guestHouse|motel|pension|spa|studio|gym|academy|store)/(\d+)', url)
    if match:
        return match.group(1)
    match = re.search(r'/([a-zA-Z]+)/(\d+)', url)
    if match:
        return match.group(2)
    match = re.search(r'/(\d+)', url)
    if match:
        return match.group(1)
    return None

def fetch_data():
    """
    Rudolph API로부터 데이터를 수집하여 표준 형식으로 반환.
    """
    try:
        # 1. Login to Rudolph
        login_url = "https://ieum.place/login"
        login_payload = {
            "nickname": "rudolph",
            "password": "rltjrWkd"
        }
        
        session = requests.Session()
        resp = session.post(login_url, data=login_payload, allow_redirects=False, timeout=15)
        if resp.status_code != 302:
            print(f"[RUDOLPH] Login failed, status code: {resp.status_code}")
            return None
            
        # 2. Fetch slots page in a single query (length: -1)
        data_url = "https://ieum.place/accounts/slots/all"
        data_headers = {
            "content-type": "application/json",
            "x-requested-with": "XMLHttpRequest",
            "Referer": "https://ieum.place/slot_list",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        payload_columns = [
            {"data": None, "name": "", "searchable": True, "orderable": False, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "id", "name": "id", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": None, "name": "", "searchable": True, "orderable": False, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "start_date", "name": "start_date", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "end_date", "name": "end_date", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "end_date", "name": "remaining_days", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "duration", "name": "duration", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "advertiser", "name": "advertiser", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "platform.name", "name": "platform_name", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "rank", "name": "rank", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "inflow_platform", "name": "inflow_platform", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "keyword", "name": "keyword", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "subkeyword", "name": "subkeyword", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "brand_store_name", "name": "brand_store_name", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "product_name", "name": "product_name", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "url", "name": "url", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "compare_url", "name": "compare_url", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "extra_field_2", "name": "extra_field_2", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "price", "name": "price", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "image_url", "name": "image_url", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "public_memo", "name": "public_memo", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "created_at", "name": "created_at", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "start_date", "name": "start_date_excel", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}},
            {"data": "end_date", "name": "end_date_excel", "searchable": True, "orderable": True, "search": {"value": "", "regex": False, "fixed": []}}
        ]

        payload = {
            "draw": 1,
            "columns": payload_columns,
            "order": [{"column": 1, "dir": "desc", "name": "id"}],
            "start": 0,
            "length": -1,
            "slot_type": "6",
            "pageLength": -1,
            "_ts": int(time.time() * 1000),
            "sort_field": "id",
            "sort_dir": "desc"
        }
        
        print("[RUDOLPH] Fetching all slots in a single query (length: -1)...")
        resp = session.post(data_url, headers=data_headers, json=payload, timeout=25)
        if resp.status_code != 200:
            print(f"[RUDOLPH] HTTP Error {resp.status_code} fetching slots")
            return None
            
        result = resp.json()
        all_slots = result.get("data", [])
        print(f"[RUDOLPH] Fetched total {len(all_slots)} slot records.")
        
        kst_today = get_kst_date()
        kst_today_iso = kst_today.isoformat()
        
        standardized_data = []
        seen_sids = set()
        
        for item in all_slots:
            sid = item.get("id")
            if sid is None or sid in seen_sids:
                continue
            
            url = str(item.get("url") or "").strip()
            dest_id = extract_place_id(url)
            if not dest_id:
                continue
                
            start_date = item.get("start_date") or kst_today_iso
            end_date = item.get("end_date") or kst_today_iso
            search_keyword = item.get("keyword") or ''
            
            # Rudolph slots work_amount is 10
            work_count = 10
            
            standardized_data.append({
                'sid': int(sid),
                'dest_id': str(dest_id).strip(),
                'work_count': work_count,
                'start_date': start_date,
                'end_date': end_date,
                'search_keyword': search_keyword,
                'target_url': f"https://m.place.naver.com/place/{dest_id}"
            })
            seen_sids.add(sid)
            
        return standardized_data
    except Exception as e:
        print(f"[RUDOLPH] Fetch Exception: {e}")
        return None
