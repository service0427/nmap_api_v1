import pymysql
import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import contextmanager

# Path adjustment to access core from external_admin folder
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from dbutils.pooled_db import PooledDB
from core.config import Config
from core.utils import get_kst_now, get_kst_date

# --- Global Connection Pool ---
db_config = Config.get_db_config()
db_config['database'] = 'nmap_api_v1' # Overwritten to read from prototype nmap_api_v1 DB

db_pool = PooledDB(
    creator=pymysql,
    mincached=2,
    maxcached=10,
    maxconnections=15,
    blocking=True,
    **db_config
)

@contextmanager
def get_db_cursor():
    conn = db_pool.connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

HAS_IS_DELETED = None

def check_is_deleted_support():
    global HAS_IS_DELETED
    if HAS_IS_DELETED is not None:
        return HAS_IS_DELETED
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM raw_slots LIKE 'is_deleted'")
            HAS_IS_DELETED = cursor.fetchone() is not None
    except Exception as e:
        print(f"Error checking is_deleted support: {e}")
        HAS_IS_DELETED = False
    return HAS_IS_DELETED

app = FastAPI(title="Nmap External Management Center - Viewer")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint restrictions: root path / is strictly forbidden
@app.get("/")
async def root_forbidden():
    raise HTTPException(status_code=403, detail="Forbidden. Access endpoints are required.")

@app.post("/api/v1/log-error")
async def log_browser_error(data: dict):
    print(f"BROWSER ERROR: {data}")
    return {"status": "ok"}

# Fetch Summary data filtered by site_id with server-side pagination (No devices data to keep it secure/viewer-only)
@app.get("/api/v1/external/summary")
async def get_external_summary(
    site: str, 
    page: int = 1, 
    page_size: int = 50, 
    search: str = "", 
    code: str = "",
    status: str = "all"
):
    if site not in ["FSD", "LUF", "LUP"]:
        raise HTTPException(status_code=400, detail="Invalid site ID")
        
    db_site = "LUF" if site in ["LUF", "LUP"] else "FSD"
    kst_now, kst_date = get_kst_now(), get_kst_date()
    
    # Calculate start of today in KST
    start_of_today = datetime.combine(kst_date, datetime.min.time())
    
    offset = (page - 1) * page_size
    if offset < 0:
        offset = 0
        
    try:
        has_is_deleted = check_is_deleted_support()
        with get_db_cursor() as cursor:
            # 1. Target overall statistics for summary cards
            is_deleted_clause = "AND is_deleted = 0" if has_is_deleted else ""
            cursor.execute(f"""
                SELECT SUM(work_count) as target 
                FROM raw_slots 
                WHERE status='on' 
                  {is_deleted_clause}
                  AND site_id = %s 
                  AND %s BETWEEN start_date AND end_date
            """, (db_site, kst_date))
            target_res = cursor.fetchone()
            target_val = int(target_res['target'] or 0) if target_res else 0
            
            # Fetch summary stats directly from tasks_log
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN status LIKE 'FAIL%%' THEN 1 ELSE 0 END) as fail
                FROM tasks_log
                WHERE site_id = %s
                  AND end_time >= %s
            """, (db_site, start_of_today))
            progress_res = cursor.fetchone()
            success_val = int(progress_res['success'] or 0) if progress_res else 0
            fail_val = int(progress_res['fail'] or 0) if progress_res else 0
            
            summary_stats = {
                "target": target_val,
                "success": success_val,
                "fail": fail_val,
                "remain": max(0, target_val - success_val)
            }
            
            # 2. Build Paginated Destinations Query with Server-side Filters
            where_clauses = ["rs.site_id = %s"]
            if has_is_deleted:
                where_clauses.append("rs.is_deleted = 0")
            params = [db_site]
            
            # Text Search filter (name or address)
            if search:
                where_clauses.append("(p.name LIKE %s OR p.address LIKE %s)")
                like_pattern = f"%{search}%"
                params.extend([like_pattern, like_pattern])
                
            # Code Search filter (dest_id)
            if code:
                where_clauses.append("rs.dest_id LIKE %s")
                like_pattern = f"%{code}%"
                params.append(like_pattern)
                
            # Status filter
            # - active: status='on' and currently running and not completed yet
            # - completed: status='on' and success_cnt >= target (limit)
            # - expired: end_date < today and end_date >= today - 7 days
            if status == "active":
                where_clauses.append("rs.status = 'on' AND %s BETWEEN rs.start_date AND rs.end_date AND IFNULL(t.success_cnt, 0) < rs.work_count")
                params.append(kst_date)
            elif status == "completed":
                where_clauses.append("rs.status = 'on' AND %s BETWEEN rs.start_date AND rs.end_date AND IFNULL(t.success_cnt, 0) >= rs.work_count")
                params.append(kst_date)
            elif status == "expired":
                where_clauses.append("rs.end_date < %s AND rs.end_date >= %s")
                seven_days_ago = kst_date - timedelta(days=7)
                params.extend([kst_date, seven_days_ago])
            else: # "all" - Today's scheduled slots
                where_clauses.append("%s BETWEEN rs.start_date AND rs.end_date")
                params.append(kst_date)
                
            where_sql = " AND ".join(where_clauses)
            
            # Count Query
            count_query = f"""
                SELECT COUNT(*) as total
                FROM raw_slots rs
                JOIN places p ON rs.dest_id = p.dest_id
                LEFT JOIN daily_progress dp ON rs.site_id = dp.site_id AND rs.sid = dp.sid AND dp.work_date = %s
                LEFT JOIN (
                    SELECT sid, site_id,
                           SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_cnt,
                           SUM(CASE WHEN status LIKE 'FAIL%%' THEN 1 ELSE 0 END) as fail_cnt
                    FROM tasks_log
                    WHERE end_time >= %s
                    GROUP BY sid, site_id
                ) t ON rs.sid = t.sid AND rs.site_id = t.site_id
                WHERE {where_sql}
            """
            cursor.execute(count_query, [kst_date, start_of_today] + params)
            total_count = cursor.fetchone()["total"]
            
            # Paginated List Query
            list_query = f"""
                SELECT p.dest_id, p.name, p.address, p.is_optimizer, p.check_status,
                       rs.work_count as target,
                       rs.status as slot_status,
                       rs.start_date,
                       rs.end_date,
                       IFNULL(t.success_cnt, 0) as success,
                       IFNULL(t.fail_cnt, 0) as fail,
                       dp.last_success_at,
                       dp.last_fail_at
                FROM raw_slots rs
                JOIN places p ON rs.dest_id = p.dest_id
                LEFT JOIN daily_progress dp ON rs.site_id = dp.site_id AND rs.sid = dp.sid AND dp.work_date = %s
                LEFT JOIN (
                    SELECT sid, site_id,
                           SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as success_cnt,
                           SUM(CASE WHEN status LIKE 'FAIL%%' THEN 1 ELSE 0 END) as fail_cnt
                    FROM tasks_log
                    WHERE end_time >= %s
                    GROUP BY sid, site_id
                ) t ON rs.sid = t.sid AND rs.site_id = t.site_id
                WHERE {where_sql}
                ORDER BY rs.status DESC, success DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(list_query, [kst_date, start_of_today] + params + [page_size, offset])
            dest_list = cursor.fetchall()
            
        return {
            "summary": summary_stats,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "destinations": dest_list
        }
    except Exception as e:
        print(f"External API Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/v1/external/history")
async def get_external_history(site: str, dest_id: str):
    if site not in ["FSD", "LUF", "LUP"]:
        raise HTTPException(status_code=400, detail="Invalid site ID")
        
    db_site = "LUF" if site in ["LUF", "LUP"] else "FSD"
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT id, start_time, end_time, duration_sec, status, result_msg
                FROM tasks_log
                WHERE site_id = %s AND dest_id = %s
                ORDER BY id DESC
                LIMIT 15
            """, (db_site, dest_id))
            history_list = cursor.fetchall()
            
        return {
            "status": "success",
            "history": history_list
        }
    except Exception as e:
        print(f"External API History Error: {e}")
        return JSONResponse(status_code=500, content={"error": "데이터베이스 조회에 실패하였습니다."})


# Page Routes for FSD and LUP
def get_no_cache_html_response():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(dir_path, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return HTMLResponse(content=content, headers=headers)

@app.get("/fsd", response_class=HTMLResponse)
async def serve_fsd():
    return get_no_cache_html_response()

@app.get("/lup", response_class=HTMLResponse)
async def serve_lup():
    return get_no_cache_html_response()

@app.get("/style.css")
async def serve_css():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    return FileResponse(os.path.join(dir_path, "style.css"))

@app.get("/app.js")
async def serve_js():
    dir_path = os.path.dirname(os.path.abspath(__file__))
    return FileResponse(os.path.join(dir_path, "app.js"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=20002)
