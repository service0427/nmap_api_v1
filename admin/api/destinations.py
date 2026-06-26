import os
import sys
from fastapi import APIRouter, HTTPException

# Path adjustment
ADMIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADMIN_DIR not in sys.path:
    sys.path.append(ADMIN_DIR)

from db import get_db_cursor
from schemas import DestinationUpdateSchema

router = APIRouter()

@router.post("/api/v1/admin/dest/update")
async def update_destination(schema: DestinationUpdateSchema):
    dest_id = schema.dest_id
    status = schema.status
    limit = schema.limit
    is_optimizer = schema.is_optimizer
    try:
        with get_db_cursor() as cursor:
            if status: 
                cursor.execute("UPDATE raw_slots SET status = %s WHERE dest_id = %s", (status, dest_id))
            if limit is not None: 
                cursor.execute("UPDATE raw_slots SET work_count = %s WHERE dest_id = %s AND status='on'", (limit, dest_id))
            if is_optimizer is not None:
                cursor.execute("UPDATE places SET is_optimizer = %s WHERE dest_id = %s", (is_optimizer, dest_id))
        return {"status": "ok"}
    except Exception as e: 
        print(f"Admin API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
