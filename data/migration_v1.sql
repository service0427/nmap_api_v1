-- 1. places 테이블 수정
ALTER TABLE places MODIFY COLUMN check_status VARCHAR(20) DEFAULT 'PENDING';
ALTER TABLE places ADD COLUMN fail_count INT DEFAULT 0 AFTER is_optimizer;

-- 2. raw_slots 테이블 수정 (target_url, search_keyword 및 Tombstone 필드 추가)
ALTER TABLE raw_slots ADD COLUMN search_keyword VARCHAR(255) DEFAULT '' AFTER dest_id;
ALTER TABLE raw_slots ADD COLUMN target_url TEXT DEFAULT NULL AFTER search_keyword;
ALTER TABLE raw_slots ADD COLUMN is_deleted TINYINT DEFAULT 0 AFTER status;
ALTER TABLE raw_slots ADD COLUMN deleted_at DATETIME DEFAULT NULL AFTER is_deleted;
ALTER TABLE raw_slots ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP AFTER deleted_at;

-- 3. slot_changelog 테이블 신규 생성
CREATE TABLE IF NOT EXISTS slot_changelog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    site_id VARCHAR(20) NOT NULL,
    slot_id VARCHAR(50) NOT NULL,
    change_type VARCHAR(20) NOT NULL,          -- CREATED, UPDATED, DELETED
    changed_column VARCHAR(50) DEFAULT NULL,   -- 변경된 컬럼 (work_count, search_keyword 등)
    old_value TEXT DEFAULT NULL,
    new_value TEXT DEFAULT NULL,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_site_slot (site_id, slot_id)
);
