# V1 슬롯 통합 설계 고도화 제안 (raw_slots 일원화 및 Places 사전 검증 루프 설계)

## 1. 개요 및 설계 방향성

기존의 `raw_slots_tmp` 테이블은 외부 사이트(ssolup, ghost2026, LUF, RUDOLPH)의 단발성/일회성 일일 작업 데이터를 프로토타입으로 동기화하기 위한 임시 테스트 목적의 테이블이었습니다. 

이를 운영 단계로 올려 완벽히 통합하고, 기기 할당 및 가시거리 최적화(`is_optimizer`, `start_pos`)를 생산성 높게 제어하기 위해 **모든 수집 대상을 `raw_slots` 테이블 하나로 일원화**하는 고도화 설계를 제안합니다.

또한, 실시간 스크래핑으로 인한 속도 저하 및 네이버 차단을 방지하기 위해 **목적지 정보(`places`)를 백그라운드에서 사전 탐색하고, 검증 실패(Fail) 시 점진적으로 재시도(Retry)하는 라이프사이클 관리 루프**를 구축합니다.

---

## 2. 통합 아키텍처 비교 (AS-IS vs TO-BE)

```mermaid
flowchart TD
    subgraph AS-IS (현재 프로토타입)
        FSD["FSD 수집 (sync_engine.py)"] -->|raw_slots 저장| RS[raw_slots]
        EXT["외부 수집 (sync_work_details.py)"] -->|raw_slots_tmp 저장| RST[raw_slots_tmp]
        RS -->|daily_aggregator.py| DP[daily_progress]
        RST -->|daily_aggregator.py| DP
    end

    subgraph TO-BE (개선 제안안)
        M_FSD["FSD 모듈"] & M_SSOL["ssolup 모듈"] & M_GHOST["ghost2026 모듈"] & M_LUF["luf 모듈"] & M_RUD["rudolph 모듈"]
        M_FSD & M_SSOL & M_GHOST & M_LUF & M_RUD -->|Fetch 표준화 데이터| SE["통합 동기화 엔진 (sync_engine.py)"]
        SE -->|단일 적재| RS_New[raw_slots]
        RS_New -->|daily_aggregator.py (쿼리 통합)| DP_New[daily_progress]
    end
```

---

## 3. 핵심 설계안

### ① `raw_slots` 단일 테이블로의 일원화 (외부 슬롯 적재 방식 개선)
- `raw_slots_tmp` 테이블과 `sync_work_details.py` 스크립트를 완전히 폐기합니다.
- `ssolup`, `ghost2026`, `luf`, `rudolph` 데이터를 수집하는 별도의 전용 모듈을 `core/sync_modules/` 하위에 작성합니다.
- 각 수집 모듈은 `fetch_data()` 함수를 구현하여 다음의 **표준화된 슬롯 형식의 리스트**를 반환합니다.
  - `sid` (int, 고유 슬롯 ID)
  - `dest_id` (str, 네이버 플레이스 ID)
  - `work_count` (int, 배정 작업량 - 루돌프는 10, 타 사이트는 API 제공값)
  - `start_date` (str, YYYY-MM-DD - LUF 등 일회성은 오늘 날짜)
  - `end_date` (str, YYYY-MM-DD - LUF 등 일회성은 오늘 날짜)
  - `search_keyword` (str, 검색어 - 루프 돌며 자동 수집 및 보완)
- `sync_engine.py`가 크론 사이클에 의해 실행되면 이 모듈들을 일괄 로드하여 `raw_slots`에 `INSERT ... ON DUPLICATE KEY UPDATE` 및 `is_deleted = 1` 처리를 표준 프로세스로 안전하게 수행합니다.

### ② 목적지 정보(`places`) 백그라운드 사전 검증 및 실패(Fail) 재시도 설계
실시간 기기 요청 처리 중에는 스크래핑을 배제하고, 백그라운드에서 크론 배치를 통해 비동기 검증(`check_status`)을 진행합니다.

1. **자동 등록 (Initial Phase)**
   - 동기화 엔진(`sync_engine.py`) 내부의 `ensure_place_info()`가 작동하여 `raw_slots`에 들어오는 모든 `dest_id`가 `places` 테이블에 있는지 검사합니다.
   - 존재하지 않는 목적지는 즉시 `places` 테이블에 `check_status = 'PENDING'`, `name = 'PENDING_등록ID'`로 1회 신속 인서트하고 할당 대기 상태로 둡니다.

2. **백그라운드 사전 검증 (Background Verification)**
   - 백그라운드 데몬인 `async_verifier.py`가 매 분 돌며 `check_status = 'PENDING'`인 업체를 조회하여 네이버 지도 모바일 API 정보를 스크래핑합니다.
   - **성공 시**: 상호명, 주소, 경도, 위도 좌표를 채워넣고 `check_status = 'VERIFIED'`로 업데이트합니다. 상호명에 특정 단어(누수, 하수구 등)가 포함되면 `is_optimizer = 1`을 자동 셋업합니다.
   - **실패 시**: 실패 원인을 로깅하고 `places.fail_count`를 1 증가시킵니다.
     - **점진적 재시도(Retry)**: `fail_count < 3`인 경우, `check_status = 'PENDING'`을 유지하여 다음 크론 주기에서 다시 검증을 시도합니다. (임시 네이버 블로킹이나 네트워크 순단 대비)
     - **최종 실패 판정**: `fail_count >= 3`이 되면 `check_status = 'FAIL'`로 기록하여 해당 목적지는 작업 할당 대상에서 영구 제외합니다.

3. **실패(Fail) 상태의 리셋/사전 탐색 절차**
   - 차단이 풀렸거나 관리자가 목적지 정보를 갱신하여 수동 재조회를 요청하는 경우, 해당 목적지의 `check_status = 'PENDING'`, `fail_count = 0`으로 데이터베이스 값을 리셋하면 백그라운드 배치 프로세스가 다음 주기에서 자동으로 사전 수집 및 검증을 재개합니다.

---

## 4. 기대 효과

1. **데이터 파이프라인 일원화 및 단순화**
   - 테이블 구조가 단순화되고 `daily_aggregator.py` 및 할당 API(`request_task`)의 조인 로직이 `raw_slots`와 `places`를 타는 하나의 정밀 쿼리로 통일되어 DB 부하가 감소하고 쿼리 속도가 향상됩니다.
2. **실패 복구력 강화**
   - 임시 에러로 검증을 실패한 업체들을 바로 영구 차단하지 않고 최대 3회 자동 재시도하여 데이터 유실율을 낮춥니다.
3. **네이버 트래픽 최적화**
   - 네이버 API 호출이 백그라운드 비동기로만 수행되므로, 대량의 게시물/슬롯이 유입되어도 클라이언트 단말기의 API 응답 속도에 0.00초의 영향도 주지 않으며 네이버 측 차단 위험도를 매우 정교하게 관리할 수 있습니다.

---

## 5. 상세 구현 로드맵

1. **`core/sync_modules/`에 ssolup, ghost2026, luf, rudolph 모듈 개발 및 이관**
2. **`sync_engine.py` 내 동기화 로직 및 `daily_aggregator.py` 쿼리 단순화 (raw_slots 대상 통일)**
3. **`async_verifier.py`에 점진적 재시도(`fail_count < 3`) 구현**
4. **테스트 및 검증 (초기화 후 전체 크론 사이클 정상 작동 확인)**

해당 고도화 설계안에 대해 동의하신다면, 즉시 구현 및 마이그레이션 작업에 착수하겠습니다. 의견을 남겨주세요!
