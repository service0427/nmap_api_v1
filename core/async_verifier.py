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
                       AND (p.updated_at IS NULL OR p.updated_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE))
                   )
                   OR (
                       r.id IS NOT NULL
                       AND (dp.fail_cnt > 0 OR dp.mismatch_cnt > 0 OR dp.miss_cnt > 0)
                       AND (p.updated_at IS NULL OR p.updated_at < DATE_SUB(NOW(), INTERVAL 1 HOUR))
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
                    
                    # 2. places 테이블 업데이트 (VERIFIED)
                    cursor.execute("""
                        UPDATE places 
                        SET name = %s, address = %s, original_address = %s, 
                            lat = %s, lng = %s, check_status = 'VERIFIED', is_optimizer = %s,
                            fail_count = 0, updated_at = %s
                        WHERE dest_id = %s
                    """, (name, address, original_address, lat, lng, is_opt, get_kst_now(), dest_id))
                    
                    # 3. raw_slots의 빈 검색어(search_keyword)를 실제 상호명으로 즉시 보완 동기화
                    cursor.execute("""
                        UPDATE raw_slots
                        SET search_keyword = %s, updated_at = %s
                        WHERE dest_id = %s AND (search_keyword = '' OR search_keyword IS NULL OR search_keyword LIKE 'PENDING_%%')
                    """, (name, get_kst_now(), dest_id))
                    
                    print(f"  [SUCCESS] {dest_id} -> {name} (VERIFIED)")
                else:
                    err_msg = info.get('message') if info else "Unknown error"
                    curr_fail = (item.get('fail_count') or 0) + 1
                    print(f"  [FAILED] {dest_id} -> Scrape failed: {err_msg} (Fail Count: {curr_fail})")
                    
                    # fail_count가 3 미만이면 PENDING 상태 유지, 3 이상이면 FAIL로 변경
                    if curr_fail < 3:
                        cursor.execute("""
                            UPDATE places 
                            SET fail_count = %s, updated_at = %s
                            WHERE dest_id = %s
                        """, (curr_fail, get_kst_now(), dest_id))
                    else:
                        cursor.execute("""
                            UPDATE places 
                            SET check_status = 'FAIL', fail_count = %s, name = %s, updated_at = %s
                            WHERE dest_id = %s
                        """, (curr_fail, f"FAILED_SCRAPE_{dest_id}", get_kst_now(), dest_id))
                    
    except Exception as e:
        print(f"[Async Verifier] Exception during run: {e}")
    finally:
        conn.close()
        print("[Async Verifier] Verification process finished.")

if __name__ == "__main__":
    run_async_verification()
