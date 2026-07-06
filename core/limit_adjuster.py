import os
import sys
import math
import pymysql

# 경로 설정
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)

from core.config import Config
from core.utils import get_kst_now, get_kst_date

def run_limit_adjuster():
    print(f"--- [Limit Adjuster] Started at {get_kst_now()} ---")
    db_config = Config.get_db_config()
    conn = pymysql.connect(**db_config, autocommit=True)
    kst_date = get_kst_date()
    kst_now = get_kst_now()
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. system_settings 테이블 자동 생성 및 초기화
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    `key` VARCHAR(50) PRIMARY KEY,
                    `value` VARCHAR(100),
                    `description` VARCHAR(255)
                )
            """)
            cursor.execute("""
                INSERT IGNORE INTO system_settings (`key`, `value`, `description`) VALUES
                ('max_total_limit', '1000', 'Default maximum total target per dest_id per day'),
                ('max_active_slots', '4', 'Default maximum active slots to distribute targets')
            """)
            
            # 2. daily_limit_adjustments 테이블 자동 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_limit_adjustments (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `work_date` DATE NOT NULL,
                    `dest_id` VARCHAR(50) NOT NULL,
                    `original_total` INT NOT NULL,
                    `adjusted_total` INT NOT NULL,
                    `limit_value` INT NOT NULL,
                    `created_at` DATETIME NOT NULL,
                    `updated_at` DATETIME NOT NULL,
                    UNIQUE KEY `uq_date_dest` (`work_date`, `dest_id`)
                )
            """)
            
            # 3. 글로벌 기본 설정값 조회
            cursor.execute("SELECT `key`, `value` FROM system_settings WHERE `key` IN ('max_total_limit', 'max_active_slots')")
            settings = {row['key']: int(row['value']) for row in cursor.fetchall()}
            
            global_total_limit = settings.get('max_total_limit', 1000)
            global_active_slots = settings.get('max_active_slots', 4)
            print(f"[Limit Adjuster] Global Config -> max_total_limit: {global_total_limit}, max_active_slots: {global_active_slots}")
            
            # 4. places 테이블의 개별 설정값 캐싱
            cursor.execute("SELECT dest_id, max_total_limit, max_active_slots FROM places")
            places_cfg = {row['dest_id']: row for row in cursor.fetchall()}
            
            # 5. 오늘의 raw_slots에서 dest_id별 오리지널 work_count 합계 구하기
            cursor.execute("""
                SELECT r.dest_id, SUM(r.work_count) as orig_total
                FROM raw_slots r
                WHERE r.status = 'on' AND r.is_deleted = 0
                  AND %s BETWEEN r.start_date AND r.end_date
                GROUP BY r.dest_id
            """, (kst_date,))
            orig_slots = {row['dest_id']: int(row['orig_total']) for row in cursor.fetchall()}
            
            # 6. 현재 daily_progress에 등록된 오늘의 dest_id별 목록 조회
            cursor.execute("""
                SELECT dest_id, SUM(total_target) as current_total, COUNT(*) as slot_count
                FROM daily_progress
                WHERE work_date = %s
                GROUP BY dest_id
            """, (kst_date,))
            progress_sums = cursor.fetchall()
            
            for row in progress_sums:
                dest_id = row['dest_id']
                current_total = int(row['current_total'])
                slot_count = int(row['slot_count'])
                
                # 개별 설정 적용 (없을 경우 글로벌 기본값)
                p_cfg = places_cfg.get(dest_id) or {}
                
                limit_t = p_cfg.get('max_total_limit')
                if limit_t is None:
                    limit_t = global_total_limit
                    
                active_s = p_cfg.get('max_active_slots')
                if active_s is None:
                    active_s = global_active_slots
                
                # 오리지널 총합 (raw_slots 합산 우선)
                orig_total = orig_slots.get(dest_id, current_total)
                
                # 오리지널 합산 또는 현재 합산이 제한 한도를 초과하는 경우 조정 처리 수행
                if orig_total > limit_t or current_total > limit_t:
                    cursor.execute("""
                        SELECT id, sid, total_target 
                        FROM daily_progress 
                        WHERE work_date = %s AND dest_id = %s
                        ORDER BY sid ASC
                    """, (kst_date, dest_id))
                    slots = cursor.fetchall()
                    N = len(slots)
                    if N == 0:
                        continue
                        
                    # 고도화 분배 알고리즘
                    # 최대 활성 제한(active_s)과 유입된 실제 슬롯 수 N 중 작은 만큼 활성화하여 균등 분배
                    A = min(N, active_s)
                    
                    if A > 0:
                        base_val = limit_t // A
                        remainder = limit_t % A
                        
                        new_targets = [0] * N
                        for i in range(A):
                            new_targets[i] = base_val + (1 if i < remainder else 0)
                    else:
                        new_targets = [0] * N
                        
                    # DB 업데이트 실행
                    for idx, slot in enumerate(slots):
                        target_val = new_targets[idx]
                        if slot['total_target'] != target_val:
                            cursor.execute("""
                                UPDATE daily_progress 
                                SET total_target = %s 
                                WHERE id = %s
                            """, (target_val, slot['id']))
                            
                    actual_adjusted_total = sum(new_targets)
                    
                    # daily_limit_adjustments에 기록 저장 (Upsert)
                    cursor.execute("""
                        INSERT INTO daily_limit_adjustments 
                            (work_date, dest_id, original_total, adjusted_total, limit_value, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                            original_total = VALUES(original_total),
                            adjusted_total = VALUES(adjusted_total),
                            limit_value = VALUES(limit_value),
                            updated_at = VALUES(updated_at)
                    """, (kst_date, dest_id, orig_total, actual_adjusted_total, limit_t, kst_now, kst_now))
                    
                    print(f"  [ADJUSTED] dest_id: {dest_id} | Orig: {orig_total} -> Adjusted: {actual_adjusted_total} (Slots: {N}, Active: {A}, MaxTotal: {limit_t}, MaxActive: {active_s})")
                    
        print("[Limit Adjuster] Completed successfully.")
    except Exception as e:
        print(f"[Limit Adjuster] ERROR: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    run_limit_adjuster()
