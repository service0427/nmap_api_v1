import random
from typing import Optional
from fastapi import APIRouter, HTTPException

from api.helpers import get_db_cursor, logger
from core.utils import get_kst_now, get_kst_date

router = APIRouter(tags=["AllocationDev"])

@router.get("/api/v1/request_task")
def request_task_get(site_id: Optional[str] = None):
    # Extremely lightweight GET handler returning ONLY destination info
    kst_now, kst_date = get_kst_now().replace(tzinfo=None), get_kst_date()
    try:
        with get_db_cursor() as cursor:
            # Query candidates randomly (unconditionally, regardless of completion status)
            # Attempt 1: Active slots today
            base_query = """
                SELECT 
                    r.site_id, r.sid, r.dest_id, p.name, p.address, p.original_address, p.lat, p.lng, 
                    r.search_keyword
                FROM raw_slots r
                JOIN places p ON r.dest_id = p.dest_id
                WHERE r.status = 'on'
                  AND r.is_deleted = 0
                  AND p.name NOT LIKE 'FAILED_SCRAPE_%%'
                  AND p.name NOT LIKE 'DELETED_%%'
                  AND p.name NOT LIKE 'INVALID_ADDR_%%'
                  AND p.lat IS NOT NULL AND p.lng IS NOT NULL AND p.lat != 0.0 AND p.lng != 0.0
                  AND p.check_status IN ('VERIFIED', 'NORMAL')
                  AND %s BETWEEN r.start_date AND r.end_date
            """
            params = [kst_date]
            if site_id:
                base_query += " AND r.site_id = %s"
                params.append(site_id)
            else:
                base_query += " AND r.site_id <> 'test'"
                
            base_query += " ORDER BY RAND() LIMIT 1"
            
            cursor.execute(base_query, tuple(params))
            task = cursor.fetchone()
            
            # Fallback 1: Active slots regardless of today's date
            if not task:
                base_query_fallback = """
                    SELECT 
                        r.site_id, r.sid, r.dest_id, p.name, p.address, p.original_address, p.lat, p.lng, 
                        r.search_keyword
                    FROM raw_slots r
                    JOIN places p ON r.dest_id = p.dest_id
                    WHERE r.status = 'on'
                      AND r.is_deleted = 0
                      AND p.name NOT LIKE 'FAILED_SCRAPE_%%'
                      AND p.name NOT LIKE 'DELETED_%%'
                      AND p.name NOT LIKE 'INVALID_ADDR_%%'
                      AND p.lat IS NOT NULL AND p.lng IS NOT NULL AND p.lat != 0.0 AND p.lng != 0.0
                      AND p.check_status IN ('VERIFIED', 'NORMAL')
                """
                params_fb = []
                if site_id:
                    base_query_fallback += " AND r.site_id = %s"
                    params_fb.append(site_id)
                else:
                    base_query_fallback += " AND r.site_id <> 'test'"
                
                base_query_fallback += " ORDER BY RAND() LIMIT 1"
                cursor.execute(base_query_fallback, tuple(params_fb))
                task = cursor.fetchone()
                
            # Fallback 2: Any verified place in places table directly (with dummy slot details)
            if not task:
                cursor.execute("""
                    SELECT 
                        p.dest_id, p.name, p.address, p.original_address, p.lat, p.lng
                    FROM places p
                    WHERE p.name NOT LIKE 'FAILED_SCRAPE_%%'
                      AND p.name NOT LIKE 'DELETED_%%'
                      AND p.name NOT LIKE 'INVALID_ADDR_%%'
                      AND p.lat IS NOT NULL AND p.lng IS NOT NULL AND p.lat != 0.0 AND p.lng != 0.0
                      AND p.check_status IN ('VERIFIED', 'NORMAL')
                    ORDER BY RAND()
                    LIMIT 1
                """)
                task = cursor.fetchone()
                
            if not task:
                raise HTTPException(status_code=404, detail="No verified tasks available")

            # Keywords lookup
            search_keyword = task.get('search_keyword')
            if not search_keyword:
                cursor.execute("SELECT keyword FROM place_keywords WHERE dest_id = %s AND status = 'on'", (task['dest_id'],))
                keywords = [row['keyword'] for row in cursor.fetchall()]
                if not keywords:
                    keywords = [task['name']]
                random.shuffle(keywords)
                search_keyword = keywords[0]

            return {
                "id": task['dest_id'],
                "target_name": task['name'],
                "search_keyword": search_keyword,
                "address": task['address'],  # Raw, original address as-is
                "lat": float(task['lat']),
                "lng": float(task['lng'])
            }
    except Exception as e:
        logger.error(f"Error in Dev Get Request Task: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
