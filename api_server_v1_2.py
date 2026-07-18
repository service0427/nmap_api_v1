import asyncio
import os
import psutil
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from api.helpers import (
    db_pool,
    get_db_cursor,
    logger,
    get_kst_now
)
import api.helpers as helpers
from api.allocation import router as allocation_router
from api.reporting import router as reporting_router
from api.system import router as system_router

from core.admin_api import register_admin_endpoints

# Initialize last_net_io for bandwidth reporting
last_net_io = psutil.net_io_counters()

async def log_system_metrics():
    global last_net_io
    while True:
        try:
            cpu, ram_mb = psutil.cpu_percent(interval=1), psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            disk = psutil.disk_usage('/')
            disk_free_gb, disk_total_gb = round(disk.free / (1024**3), 2), round(disk.total / (1024**3), 2)
            curr_net_io = psutil.net_io_counters()
            net_sent_mb, net_recv_mb = round((curr_net_io.bytes_sent - last_net_io.bytes_sent) / (1024 * 1024), 2), round((curr_net_io.bytes_recv - last_net_io.bytes_recv) / (1024 * 1024), 2)
            last_net_io = curr_net_io
            
            # Read metrics from the shared helpers module
            devices_cnt = len(helpers.active_devices)
            req_cnt = helpers.request_counter
            
            # Reset metrics for the next cycle
            helpers.request_counter = 0
            helpers.active_devices.clear()
            
            kst_now = get_kst_now()
            with get_db_cursor() as cursor:
                pool_used = db_pool._conns[0].size if hasattr(db_pool, '_conns') else 0
                cursor.execute("""
                    INSERT INTO system_metrics (heartbeat_at, cpu_usage, ram_usage_mb, disk_free_gb, disk_total_gb, active_devices, total_req, net_sent_mb, net_recv_mb, db_pool_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (kst_now, cpu, ram_mb, disk_free_gb, disk_total_gb, devices_cnt, req_cnt, net_sent_mb, net_recv_mb, pool_used))
                
        except Exception as e:
            logger.error(f"Monitoring Error: {e}")
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up API Server v1.2: initiating background monitoring task.")
    # Disabled system metrics logging for v1.2 test server
    monitoring_task = None
    yield
    logger.info("Shutting down API Server v1.2: canceling background monitoring task.")
    if monitoring_task:
        monitoring_task.cancel()
    try:
        if monitoring_task:
            await monitoring_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Nmap Production API v1.2 (Test)", lifespan=lifespan)

# Register Admin Dashboard Static and Router Endpoints
app.mount("/admin", StaticFiles(directory="admin", html=True), name="admin")
register_admin_endpoints(app, get_db_cursor=get_db_cursor, active_devices=helpers.active_devices)

# Mount APIRouters
app.include_router(allocation_router)
app.include_router(reporting_router)
app.include_router(system_router)

if __name__ == "__main__":
    import uvicorn
    # v1_1 runs on port 8011
    uvicorn.run(app, host="0.0.0.0", port=8013)
