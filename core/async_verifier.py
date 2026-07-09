import os
import sys
import time
import random
import re
import pymysql

# Path adjustment
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)

from core.config import Config
from core.scraper import NaverPlaceScraper
from core.utils import get_kst_now, get_kst_date


def run_async_verification():
    print(f"--- [Async Verifier] Started at {get_kst_now()} ---")
    db_config = Config.get_db_config()
    conn = pymysql.connect(**db_config, autocommit=True)
    scraper = NaverPlaceScraper()
    try:
        with conn.cursor() as cursor:
            # Query all PENDING places, OR places active today that are in FAIL state, or have missing details,
            # OR places that have task failures (fail_cnt > 0, mismatch_cnt > 0, etc.) today to re-verify if their details changed.
            cursor.execute("""
                SELECT DISTINCT p.dest_id, p.fail_count, p.check_status
                FROM places p
                LEFT JOIN raw_slots r ON p.dest_id = r.dest_id AND r.status = 'on' AND r.is_deleted = 0 AND %s BETWEEN r.start_date AND r.end_date
                LEFT JOIN daily_progress dp ON p.dest_id = dp.dest_id AND dp.work_date = %s
                WHERE p.check_status = 'PENDING'
                   OR (
                       r.id IS NOT NULL 
                       AND (p.check_status = 'FAIL' OR p.name = '' OR p.name LIKE 'FAILED_SCRAPE_%%' OR p.lat IS NULL OR p.lng IS NULL)
                       AND (p.last_checked_at IS NULL OR p.last_checked_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE))
                   )
                ORDER BY p.check_status ASC, p.created_at ASC
            """, (get_kst_date(), get_kst_date()))
            pending_items = cursor.fetchall()
            if not pending_items:
                print("[Async Verifier] No PENDING or active stuck places to verify.")
                return
                
            print(f"[Async Verifier] Found {len(pending_items)} places to verify (including active stuck retries).")
            
            for item in pending_items:
                dest_id = item['dest_id']
                print(f"[Async Verifier] Verifying dest_id: {dest_id}...")
                
                # 네이버 차단 방지를 위한 요청 전 딜레이 (1.5 ~ 3.5초 랜덤)
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)
                
                # 플레이스 상세 정보 스크래핑
                info = scraper.fetch_place_info(dest_id)
                
                if info and "error" not in info:
                    name = info['name']
                    address = info['address']
                    original_address = info.get('original_address')
                    lat = info['lat']
                    lng = info['lng']
                    is_opt = 1 if re.search(r'누수|청소|하수구|변기|이사|싱크대|뚫음', name) else 0
                    
                    # 주소가 비어있거나 한국 위경도 범위를 벗어나는 해외 업체의 경우 강제 FAIL 처리
                    is_invalid = False
                    if not address or address.strip() == '':
                        is_invalid = True
                    else:
                        try:
                            lat_f = float(lat)
                            lng_f = float(lng)
                            # 대한민국 위경도 대략적 한계 범위 (위도 33~39, 경도 124~132)
                            if not (33.0 <= lat_f <= 39.0 and 124.0 <= lng_f <= 132.0):
                                is_invalid = True
                        except:
                            is_invalid = True

                    if is_invalid:
                        print(f"  [INVALID_PLACE] {dest_id} -> No address or foreign coordinates (lat: {lat}, lng: {lng}). Flagging as FAIL.")
                        cursor.execute("""
                            UPDATE places 
                            SET check_status = 'FAIL', fail_count = 0, name = %s, last_checked_at = %s
                            WHERE dest_id = %s
                        """, (f"INVALID_ADDR_{dest_id}", get_kst_now(), dest_id))
                        continue
                    
                    # Check if anything changed
                    cursor.execute("SELECT name, address, original_address, lat, lng FROM places WHERE dest_id = %s", (dest_id,))
                    old_row = cursor.fetchone()
                    
                    changed = False
                    if old_row:
                        old_lat = old_row.get('lat')
                        old_lng = old_row.get('lng')
                        if old_row.get('name') != name or old_row.get('address') != address or old_row.get('original_address') != original_address:
                            changed = True
                        elif old_lat is None or old_lng is None:
                            changed = True
                        elif abs(float(old_lat) - float(lat)) > 0.0001 or abs(float(old_lng) - float(lng)) > 0.0001:
                            changed = True
                    else:
                        changed = True
                            
                    # 2. places 테이블 업데이트 (VERIFIED, fail_count는 0으로 고정)
                    cursor.execute("""
                        UPDATE places 
                        SET name = %s, address = %s, original_address = %s, 
                            lat = %s, lng = %s, check_status = 'VERIFIED', 
                            is_optimizer = IF(is_optimizer = 1, 1, %s),
                            fail_count = 0, last_checked_at = %s
                        WHERE dest_id = %s
                    """, (name, address, original_address, lat, lng, is_opt, get_kst_now(), dest_id))
                    
                    # 2b. daily_progress 테이블의 오늘 실패 카운트 초기화 (정보 변경 시에만 자동 잠금 해제)
                    if changed:
                        cursor.execute("""
                            UPDATE daily_progress 
                            SET fail_cnt = 0, miss_cnt = 0, mismatch_cnt = 0, timeout_cnt = 0 
                            WHERE dest_id = %s AND work_date = %s
                        """, (dest_id, get_kst_date()))
                        print(f"  [INFO] Details changed for {dest_id}. Resetting daily progress failures.")
                    
                    # 3. raw_slots의 빈 검색어(search_keyword)를 실제 상호명으로 즉시 보완 동기화
                    cursor.execute("""
                        UPDATE raw_slots
                        SET search_keyword = %s, updated_at = %s
                        WHERE dest_id = %s AND (search_keyword = '' OR search_keyword IS NULL OR search_keyword LIKE 'PENDING_%%')
                    """, (name, get_kst_now(), dest_id))
                    
                    print(f"  [SUCCESS] {dest_id} -> {name} (VERIFIED)")
                else:
                    err_msg = info.get('message') if info else "Unknown error"
                    err_code = info.get('error') if info else "unknown"
                    status_code = info.get('status_code') if info else None
                    
                    is_permanent = (err_code == 'no_name' or status_code == 404)
                    
                    if is_permanent:
                        print(f"  [DELETED_PLACE] {dest_id} -> Deleted/Closed on Naver Map (error: {err_code}, status: {status_code}). Flagging as FAIL.")
                        cursor.execute("""
                            UPDATE places 
                            SET check_status = 'FAIL', fail_count = 0, name = %s, last_checked_at = %s
                            WHERE dest_id = %s
                        """, (f"DELETED_{dest_id}", get_kst_now(), dest_id))
                    else:
                        print(f"  [FAILED] {dest_id} -> Scrape failed: {err_msg}")
                        # Increment fail_count for temporary errors. If it fails 10 times consecutively, mark as FAIL
                        cursor.execute("SELECT fail_count FROM places WHERE dest_id = %s", (dest_id,))
                        fc_row = cursor.fetchone()
                        curr_fc = fc_row['fail_count'] if fc_row else 0
                        new_fc = curr_fc + 1
                        
                        if new_fc >= 10:
                            print(f"  [FAILED_LIMIT] {dest_id} -> Failed to scrape 10 times consecutively. Flagging as FAIL.")
                            cursor.execute("""
                                UPDATE places 
                                SET check_status = 'FAIL', fail_count = 0, name = %s, last_checked_at = %s
                                WHERE dest_id = %s
                            """, (f"FAILED_SCRAPE_{dest_id}", get_kst_now(), dest_id))
                        else:
                            cursor.execute("""
                                UPDATE places 
                                SET check_status = 'PENDING', fail_count = %s, last_checked_at = %s
                                WHERE dest_id = %s
                            """, (new_fc, get_kst_now(), dest_id))
                    
    except Exception as e:
        print(f"[Async Verifier] Exception during run: {e}")
    finally:
        conn.close()
        print("[Async Verifier] Verification process finished.")

if __name__ == "__main__":
    run_async_verification()
