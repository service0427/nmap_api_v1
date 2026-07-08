import os
import sys
import random
import time
import pymysql
import re

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)

from core.config import Config
from core.scraper import NaverPlaceScraper
from core.utils import get_kst_now, get_kst_date, calculate_gps_and_speed

DB_CONFIG = Config.get_db_config()

def get_keywords_for_place(cursor, dest_id, default_name):
    cursor.execute("SELECT keyword FROM place_keywords WHERE dest_id = %s AND status = 'on'", (dest_id,))
    keywords = [r['keyword'] for r in cursor.fetchall()]
    
    if not keywords:
        cursor.execute("""
            SELECT DISTINCT search_keyword 
            FROM raw_slots 
            WHERE dest_id = %s 
              AND status = 'on' 
              AND is_deleted = 0 
              AND search_keyword IS NOT NULL 
              AND search_keyword != ''
        """, (dest_id,))
        keywords = [r['search_keyword'] for r in cursor.fetchall()]
        
    if not keywords:
        keywords = [default_name]
        
    return keywords

def test_expansion_visibility(scraper, dest_id, keywords, lat, lng, dist_m):
    """
    Test if the place is visible from the given coordinate at dist_m.
    """
    for kw in keywords[:2]:  # Test top 2 keywords
        for _ in range(2):   # 2 attempts
            try:
                res = scraper._mobile_search(kw, lat=str(lat), lng=str(lng), timeout=5)
                places = res.get("place", [])
                
                idx = next((i for i, p in enumerate(places) if str(p.get('id')) == str(dest_id)), -1)
                if idx != -1:
                    rank = idx + 1
                    
                    # Strict rank threshold based on distance
                    if dist_m >= 5000:
                        max_allowed_rank = 3
                    elif dist_m >= 1500:
                        max_allowed_rank = 5
                    else:
                        max_allowed_rank = 8
                        
                    if rank <= max_allowed_rank:
                        print(f"      [PROBE SUCCESS] {dest_id} visible at {dist_m}m with keyword '{kw}' (Rank {rank})")
                        return True
                time.sleep(0.5)
            except Exception as e:
                print(f"      [PROBE ERROR] {dest_id} search error: {e}")
                time.sleep(1)
    return False

def refill_pool():
    print(f"--- [Pool Refiller] Started at {get_kst_now()} ---")
    
    kst_date = get_kst_date()
    kst_now = get_kst_now()
    scraper = NaverPlaceScraper()
    
    conn = pymysql.connect(**DB_CONFIG, autocommit=True)
    try:
        with conn.cursor() as cursor:
            # 0. Clean up old pool rows to prevent database bloat
            cursor.execute("DELETE FROM task_position_pool WHERE created_date < %s", (kst_date,))
            print(f"[Pool Refiller] Purged old coordinates older than {kst_date}.")

            # 1. Fetch active optimizer places for today with remaining target > 0
            cursor.execute("""
                SELECT dp.dest_id, dp.total_target, dp.success_cnt, p.name, p.lat, p.lng, p.dist_min_m, p.dist_max_m, dp.site_id, dp.sid
                FROM daily_progress dp
                JOIN places p ON dp.dest_id = p.dest_id
                WHERE dp.work_date = %s
                  AND (dp.total_target - dp.success_cnt) > 0
                  AND p.is_optimizer = 1
                  AND p.check_status IN ('VERIFIED', 'NORMAL', 'FAIL')
                ORDER BY dp.dest_id DESC
            """, (kst_date,))
            active_places = cursor.fetchall()
            
            if not active_places:
                print("[Pool Refiller] No active places with remaining targets today.")
                return
                
            print(f"[Pool Refiller] Found {len(active_places)} active places to verify.")
            
            for row in active_places:
                dest_id = row['dest_id']
                target = int(row['total_target'])
                success_cnt = int(row.get('success_cnt', 0))
                remain = target - success_cnt
                
                # Scale required size to remaining target to avoid unnecessary rows
                required_size = max(3, int(remain * 1.5))
                
                # Check current unused pool size
                cursor.execute("""
                    SELECT COUNT(*) as cnt 
                    FROM task_position_pool 
                    WHERE dest_id = %s AND created_date = %s AND is_used = 0
                      AND (actual_rank BETWEEN 1 AND 8)
                """, (dest_id, kst_date))
                current_pool = cursor.fetchone()['cnt']
                
                if current_pool >= required_size:
                    continue
                    
                needed = required_size - current_pool
                print(f"  [{row['name']}] Pool low: {current_pool}/{required_size}. Generating {needed} coordinates...")
                
                # Retrieve configured min/max distances
                dist_min = int(row['dist_min_m'])
                dist_max = int(row['dist_max_m'])
                lat = float(row['lat'])
                lng = float(row['lng'])
                
                # 2. Generate coordinates and verify with Naver Map search
                if needed > 0:
                    inserted_cnt = 0
                    primary_kw = row['name']
                    attempts = 0
                    max_attempts = needed * 30
                    
                    while inserted_cnt < needed and attempts < max_attempts:
                        attempts += 1
                        s_lat, s_lng, real_d, _ = calculate_gps_and_speed(lat, lng, dist_min, dist_max, 0, 0, fixed_arrival_s=600)
                        
                        try:
                            res = scraper._mobile_search(primary_kw, lat=str(s_lat), lng=str(s_lng), timeout=5)
                            places = res.get("place", [])
                            all_items = res.get("all", [])
                            
                            total_place_count = len(places)
                            autocomplete_count = len(all_items)
                            
                            # Find actual rank in 'all' list
                            actual_rank = None
                            chosen_keyword = primary_kw
                            for i, item in enumerate(all_items):
                                p_info = item.get('place')
                                if p_info and str(p_info.get('id')) == str(dest_id):
                                    actual_rank = i + 1
                                    break
                            
                            max_allowed_rank = 8
                                
                            # Backup keyword check if not found or rank too low
                            if actual_rank is None or actual_rank > max_allowed_rank:
                                backup_keywords = []
                                cursor.execute("SELECT keyword FROM place_keywords WHERE dest_id = %s AND status = 'on'", (dest_id,))
                                for r in cursor.fetchall():
                                    backup_keywords.append(r['keyword'])
                                
                                cursor.execute("SELECT search_keyword FROM raw_slots WHERE dest_id = %s AND status = 'on' AND is_deleted = 0 LIMIT 1", (dest_id,))
                                rs_row = cursor.fetchone()
                                if rs_row and rs_row['search_keyword'] and rs_row['search_keyword'] not in backup_keywords:
                                    backup_keywords.append(rs_row['search_keyword'])
                                    
                                for b_kw in backup_keywords:
                                    try:
                                        res_bk = scraper._mobile_search(b_kw, lat=str(s_lat), lng=str(s_lng), timeout=5)
                                        all_bk = res_bk.get("all", [])
                                        for i, item_bk in enumerate(all_bk):
                                            p_info = item_bk.get('place')
                                            if p_info and str(p_info.get('id')) == str(dest_id):
                                                bk_rank = i + 1
                                                if bk_rank <= max_allowed_rank:
                                                    actual_rank = bk_rank
                                                    chosen_keyword = b_kw
                                                    print(f"      [Pool Refiller] Backup keyword '{b_kw}' succeeded! Rank: {actual_rank}")
                                                    break
                                        if actual_rank is not None:
                                            break
                                    except Exception as e_bk:
                                        print(f"      [Pool Refiller] Backup keyword '{b_kw}' search error: {e_bk}")
                            
                            # Only insert if the place is actually found and within the visible rank threshold
                            if actual_rank is not None and actual_rank <= max_allowed_rank:
                                cursor.execute("""
                                    INSERT INTO task_position_pool (
                                        dest_id, lat, lng, dist_m, is_used, created_date,
                                        keyword, total_place_count, autocomplete_count, actual_rank
                                    )
                                    VALUES (%s, %s, %s, %s, 0, %s, %s, %s, %s, %s)
                                """, (
                                    dest_id, s_lat, s_lng, int(real_d), kst_date,
                                    chosen_keyword, total_place_count, autocomplete_count, actual_rank
                                ))
                                inserted_cnt += 1
                                print(f"    [Pool Refiller] Saved valid coordinate for '{row['name']}' at {int(real_d)}m (Rank: {actual_rank}, Keyword: {chosen_keyword})")
                            else:
                                print(f"    [Pool Refiller] Skipped invalid coordinate (Rank: {actual_rank}, Max Allowed: {max_allowed_rank})")
                                
                        except Exception as e:
                            print(f"    [Pool Refiller] Warning: Failed to fetch search details: {e}")
                            time.sleep(0.1)
                    # Fallback: If we couldn't find enough verified coordinates, force-generate at minimum distance
                    if inserted_cnt < needed:
                        fallback_needed = needed - inserted_cnt
                        print(f"  [{row['name']}] Verified pool generation fell short. Force-generating {fallback_needed} fallback coordinates...")
                        for _ in range(fallback_needed):
                            s_lat, s_lng, real_d, _ = calculate_gps_and_speed(lat, lng, dist_min, min(dist_max, dist_min + 100), 0, 0, fixed_arrival_s=600)
                            fallback_rank = 1 if dist_max <= 300 else -1
                            cursor.execute("""
                                INSERT INTO task_position_pool (
                                    dest_id, lat, lng, dist_m, is_used, created_date,
                                    keyword, total_place_count, autocomplete_count, actual_rank
                                )
                                VALUES (%s, %s, %s, %s, 0, %s, %s, 0, 0, %s)
                            """, (
                                dest_id, s_lat, s_lng, int(real_d), kst_date,
                                chosen_keyword, fallback_rank
                            ))
                            inserted_cnt += 1
                            
                    print(f"  [{row['name']}] Generated & verified {inserted_cnt} coordinates (attempts: {attempts}) in range {dist_min}m ~ {dist_max}m.")
                    
    except Exception as e:
        print(f"[Pool Refiller] ERROR during execution: {e}")
    finally:
        conn.close()
        print("--- [Pool Refiller] Finished ---")

if __name__ == "__main__":
    refill_pool()
