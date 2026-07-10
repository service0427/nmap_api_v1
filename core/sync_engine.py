import os
import sys
import hashlib
import json
import pymysql
import importlib
import argparse
import re
from datetime import datetime, date, timedelta

# 경로 설정
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)

from core.config import Config
from core.scraper import NaverPlaceScraper
from core.utils import get_kst_now, get_kst_date

# 공통 설정 및 인스턴스
HASH_DIR = os.path.join(PROJECT_DIR, "data/hashes")
if not os.path.exists(HASH_DIR):
    os.makedirs(HASH_DIR)

scraper_instance = NaverPlaceScraper()

def get_hash(data):
    return hashlib.md5(str(data).encode()).hexdigest()

def log_sync_summary(cursor, site_id, fetched, inserted, updated, deleted, error=None):
    kst_now = get_kst_now()
    cursor.execute("""
        INSERT INTO sync_log_summary (site_id, sync_time, total_fetched, inserted_cnt, updated_cnt, deleted_cnt, error_msg)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (site_id, kst_now, fetched, inserted, updated, deleted, error))
    return cursor.lastrowid

def log_sync_detail(cursor, summary_id, site_id, sid, action, old_data=None, new_data=None):
    cursor.execute("""
        INSERT INTO sync_log_detail (summary_id, site_id, sid, action_type, old_data, new_data)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (summary_id, site_id, sid, action, json.dumps(old_data) if old_data else None, json.dumps(new_data) if new_data else None))

def ensure_place_info(cursor, dest_id, force_update=False):
    # 1. 이미 존재하는지 조회
    cursor.execute("SELECT dest_id, name, check_status FROM places WHERE dest_id = %s", (dest_id,))
    row = cursor.fetchone()
    
    # 기존 정보가 존재하면 유니크 관리 업체의 정보 훼손을 막기 위해 덮어쓰기 없이 즉시 스킵
    if row:
        return True

    # 캐시가 없는 완전히 새로운 dest_id는 'PENDING'으로 신속 등록하여 비동기 후처리기가 긁어가도록 위임
    cursor.execute("""
        INSERT IGNORE INTO places (dest_id, name, check_status)
        VALUES (%s, %s, 'PENDING')
    """, (dest_id, f"PENDING_{dest_id}"))
    return True

def process_sync(site_id, standardized_data, dry_run=False):
    if dry_run:
        print(f"\n--- [DRY-RUN] Data for {site_id} ({len(standardized_data)} items) ---")
        for item in standardized_data[:3]: print(f"  Sample: {item}")
        return

    print(f"--- [Sync] Processing {site_id} ---")
    
    conn = pymysql.connect(**Config.get_db_config(), autocommit=True)
    try:
        with conn.cursor() as cursor:
            standardized_data.sort(key=lambda x: x['sid'])
            new_hash = hashlib.md5(json.dumps(standardized_data, default=str).encode()).hexdigest()
            
            hash_file = os.path.join(HASH_DIR, f"sync_hash_{site_id}.txt")
            if os.path.exists(hash_file):
                with open(hash_file, "r") as f:
                    if f.read().strip() == new_hash:
                        cursor.execute("SELECT COUNT(*) as cnt FROM raw_slots WHERE site_id = %s AND is_deleted = 0", (site_id,))
                        if cursor.fetchone()['cnt'] > 0:
                            print(f"[{site_id}] No changes detected via hash.")
                            return

            cursor.execute("SELECT sid, dest_id, search_keyword, target_url, work_count, start_date, end_date, config_hash, status, is_deleted FROM raw_slots WHERE site_id = %s", (site_id,))
            current_state = {row['sid']: row for row in cursor.fetchall()}
            
            inserted, updated, deleted = 0, 0, 0
            summary_id = log_sync_summary(cursor, site_id, len(standardized_data), 0, 0, 0)
            
            new_sid_list = set()
            for item in standardized_data:
                sid = item['sid']
                new_sid_list.add(sid)
                
                # 로컬 daily_progress의 success_cnt, fail_cnt, alloc_fail_cnt를 가져와 성공률 기반 판정
                cursor.execute("""
                    SELECT IFNULL(success_cnt, 0) as success_cnt,
                           IFNULL(fail_cnt, 0) as fail_cnt,
                           IFNULL(alloc_fail_cnt, 0) as alloc_fail_cnt
                    FROM daily_progress 
                    WHERE work_date = %s AND site_id = %s AND dest_id = %s
                """, (get_kst_date(), site_id, item['dest_id']))
                dp_row = cursor.fetchone()
                
                success_cnt = dp_row['success_cnt'] if dp_row else 0
                fail_cnt = dp_row['fail_cnt'] if dp_row else 0
                alloc_fail_cnt = dp_row['alloc_fail_cnt'] if dp_row else 0
                total_fail = fail_cnt + alloc_fail_cnt
                total_runs = success_cnt + total_fail

                # 실패가 2회 이상 발생했고, 전체 시도 중 성공률이 60% 이하인 경우 고장 의심 대상으로 판정
                is_high_failure = False
                if total_runs > 0:
                    success_rate = success_cnt / total_runs
                    if success_rate <= 0.6 and total_fail >= 2:
                        is_high_failure = True

                ensure_place_info(cursor, item['dest_id'], force_update=is_high_failure)
                
                if is_high_failure:
                    cursor.execute("SELECT dist_max_m FROM places WHERE dest_id = %s", (item['dest_id'],))
                    p_dist_row = cursor.fetchone()
                    
                    # 기존 주행 거리가 너무 먼 경우(3km 초과)에만 점진적 케어 시작을 위해 1000m ~ 3000m 범위로 초기화
                    curr_max = p_dist_row['dist_max_m'] if p_dist_row and p_dist_row['dist_max_m'] is not None else 10000
                    if curr_max > 3000:
                        cursor.execute("""
                            UPDATE places 
                            SET is_optimizer = 1,
                                dist_min_m = 1000,
                                dist_max_m = 3000
                            WHERE dest_id = %s 
                        """, (item['dest_id'],))
                        cursor.execute("DELETE FROM task_position_pool WHERE dest_id = %s AND dist_m > 3000", (item['dest_id'],))
                    else:
                        cursor.execute("""
                            UPDATE places 
                            SET is_optimizer = 1
                            WHERE dest_id = %s 
                        """, (item['dest_id'],))
                
                # 모든 슬롯에 대해 daily_progress 생성 및 total_target 동기화
                succ_cnt = item.get('success_count') or 0
                cursor.execute("""
                    INSERT INTO daily_progress (work_date, site_id, dest_id, sid, success_cnt, fail_cnt, alloc_fail_cnt, last_dist_m, total_target)
                    VALUES (%s, %s, %s, %s, %s, 0, 0, 800, %s)
                    ON DUPLICATE KEY UPDATE dest_id = VALUES(dest_id), total_target = VALUES(total_target), success_cnt = GREATEST(success_cnt, VALUES(success_cnt))
                """, (get_kst_date(), site_id, item['dest_id'], item['sid'], succ_cnt, item['work_count']))
                
                # 1일 1회성 등 검색어(search_keyword) 유입 누락 시 places.name으로 자동 보완
                search_keyword = item.get('search_keyword') or ''
                if not search_keyword:
                    cursor.execute("SELECT name FROM places WHERE dest_id = %s", (item['dest_id'],))
                    p_row = cursor.fetchone()
                    if p_row and p_row['name']:
                        search_keyword = p_row['name']
                
                record_str = f"{site_id}_{sid}_{item['dest_id']}_{search_keyword}_{item.get('target_url') or ''}_{item['work_count']}_{item['start_date']}_{item['end_date']}"
                config_hash = hashlib.md5(record_str.encode()).hexdigest()
                
                if sid not in current_state:
                    cursor.execute("""
                        INSERT INTO raw_slots (site_id, sid, dest_id, search_keyword, target_url, work_count, start_date, end_date, config_hash, status, is_deleted, deleted_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'on', 0, NULL, %s)
                    """, (site_id, sid, item['dest_id'], search_keyword, item.get('target_url'), item['work_count'], item['start_date'], item['end_date'], config_hash, get_kst_now()))
                    
                    cursor.execute("""
                        INSERT INTO slot_changelog (site_id, slot_id, change_type, changed_column, old_value, new_value)
                        VALUES (%s, %s, 'CREATED', NULL, NULL, %s)
                    """, (site_id, sid, json.dumps(item, default=str)))
                    inserted += 1
                else:
                    old = current_state[sid]
                    if old['config_hash'] != config_hash or old['status'] != 'on' or old['is_deleted'] == 1:
                        cursor.execute("""
                            UPDATE raw_slots 
                            SET dest_id=%s, search_keyword=%s, target_url=%s, work_count=%s, start_date=%s, end_date=%s, config_hash=%s, status='on', is_deleted=0, deleted_at=NULL, updated_at=%s
                            WHERE site_id=%s AND sid=%s
                        """, (item['dest_id'], search_keyword, item.get('target_url'), item['work_count'], item['start_date'], item['end_date'], config_hash, get_kst_now(), site_id, sid))
                        
                        # 이력 추적 기록
                        changes = []
                        if old['dest_id'] != item['dest_id']: changes.append(('dest_id', old['dest_id'], item['dest_id']))
                        if old.get('search_keyword') != search_keyword: changes.append(('search_keyword', old.get('search_keyword'), search_keyword))
                        if old.get('target_url') != item.get('target_url'): changes.append(('target_url', old.get('target_url'), item.get('target_url')))
                        if old['work_count'] != item['work_count']: changes.append(('work_count', str(old['work_count']), str(item['work_count'])))
                        if str(old['start_date']) != str(item['start_date']): changes.append(('start_date', str(old['start_date']), str(item['start_date'])))
                        if str(old['end_date']) != str(item['end_date']): changes.append(('end_date', str(old['end_date']), str(item['end_date'])))
                        if old['is_deleted'] == 1: changes.append(('is_deleted', '1', '0'))
                        
                        for col, ov, nv in changes:
                            cursor.execute("""
                                INSERT INTO slot_changelog (site_id, slot_id, change_type, changed_column, old_value, new_value)
                                VALUES (%s, %s, 'UPDATED', %s, %s, %s)
                            """, (site_id, sid, col, ov, nv))
                        
                        updated += 1
            
            for sid, old in current_state.items():
                if sid not in new_sid_list and old['is_deleted'] == 0:
                    cursor.execute("""
                        UPDATE raw_slots 
                        SET status='off', is_deleted=1, deleted_at=%s, updated_at=%s 
                        WHERE site_id=%s AND sid=%s
                    """, (get_kst_now(), get_kst_now(), site_id, sid))
                    
                    cursor.execute("""
                        INSERT INTO slot_changelog (site_id, slot_id, change_type, changed_column, old_value, new_value)
                        VALUES (%s, %s, 'DELETED', NULL, NULL, NULL)
                    """, (site_id, sid))
                    deleted += 1
            
            cursor.execute("UPDATE sync_log_summary SET inserted_cnt=%s, updated_cnt=%s, deleted_cnt=%s WHERE id=%s", (inserted, updated, deleted, summary_id))
            with open(hash_file, "w") as f: f.write(new_hash)
            print(f"[{site_id}] Completed: Ins={inserted}, Upd={updated}, Del={deleted}")
            
    except Exception as e:
        print(f"[{site_id}] Sync Error: {e}")
        raise e
    finally:
        conn.close()

def run_all_syncs(dry_run=False, force=False):
    modules_dir = os.path.join(os.path.dirname(__file__), "sync_modules")
    if not os.path.exists(modules_dir): return
    for filename in os.listdir(modules_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            try:
                module = importlib.import_module(f"core.sync_modules.{module_name}")
                if hasattr(module, "fetch_data"):
                    data = module.fetch_data()
                    if data is not None:
                        process_sync(module_name.upper(), data, dry_run=dry_run)
            except Exception as e: 
                print(f"[{module_name.upper()}] ERROR: {e}")

if __name__ == "__main__":
    # Exclusive Lock to prevent overlapping execution
    import fcntl
    lock_file_path = "/tmp/nmap_sync_engine.lock"
    lock_file = open(lock_file_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("[Sync Engine] Skip: Another instance is already running.")
        sys.exit(0)

    parser = argparse.ArgumentParser(description="Nmap API Sync Engine")
    parser.add_argument("--dry-run", action="store_true", help="Print collected data without updating database")
    parser.add_argument("--force", action="store_true", help="Force sync bypassing time/cron restrictions")
    args = parser.parse_args()
    run_all_syncs(dry_run=args.dry_run, force=args.force)
