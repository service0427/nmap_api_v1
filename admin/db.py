import pymysql
import os
import sys
from contextlib import contextmanager
from dbutils.pooled_db import PooledDB

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core.config import Config

# --- Global Connection Pool ---
db_config = Config.get_db_config()
db_config['database'] = 'nmap_api_v1'  # Prototype nmap_api_v1 DB

db_pool = PooledDB(
    creator=pymysql,
    mincached=2,
    maxcached=10,
    maxconnections=20,
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
