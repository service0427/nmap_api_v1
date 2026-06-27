import os
import sys
import subprocess
import glob
from datetime import datetime, timedelta

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)

from core.config import Config
from core.utils import get_kst_now

def run_backup():
    kst_now = get_kst_now()
    print(f"--- DB Backup Started at {kst_now} ---")
    
    # 1. Load config
    db_cfg = Config.get_db_config()
    db_host = db_cfg.get('host')
    db_user = db_cfg.get('user')
    db_pass = db_cfg.get('password')
    db_name = db_cfg.get('database')
    db_port = db_cfg.get('port', 3306)
    db_socket = db_cfg.get('unix_socket')
    
    # 2. Setup backup directory
    backup_dir = "/home/tech/db_backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)
        
    # File name format: nmap_api_v1_backup_YYYYMMDD_HHMMSS.sql.gz
    timestamp = kst_now.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{db_name}_backup_{timestamp}.sql.gz"
    backup_filepath = os.path.join(backup_dir, backup_filename)
    
    # 3. Construct and run mysqldump command
    # Use --single-transaction and --quick to prevent locking live tables
    cmd = [
        "mysqldump",
        f"-u{db_user}",
        f"-p{db_pass}",
        "--single-transaction",
        "--quick",
        "--lock-tables=false",
    ]
    if db_host:
        cmd.extend([f"-h{db_host}", f"-P{db_port}"])
    elif db_socket:
        cmd.append(f"--socket={db_socket}")
        
    cmd.append(db_name)
    
    try:
        # Pipe mysqldump stdout to gzip and save to file
        with open(backup_filepath, "wb") as f_out:
            dump_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            gzip_proc = subprocess.Popen(["gzip", "-c"], stdin=dump_proc.stdout, stdout=f_out)
            
            # Allow dump_proc to receive a SIGPIPE if gzip_proc exits.
            if dump_proc.stdout:
                dump_proc.stdout.close()
                
            stdout_err, stderr_err = dump_proc.communicate()
            gzip_proc.communicate()
            
            if dump_proc.returncode != 0:
                err_msg = stderr_err.decode().strip()
                print(f"  [ERROR] mysqldump failed with code {dump_proc.returncode}: {err_msg}")
                # Remove partial file if failed
                if os.path.exists(backup_filepath):
                    os.remove(backup_filepath)
                return False
                
        file_size = os.path.getsize(backup_filepath) / (1024 * 1024)
        print(f"  [SUCCESS] Backup saved to: {backup_filepath} ({file_size:.2f} MB)")
        
        # 4. Clean up backups older than 30 days
        print("  Cleaning up backups older than 30 days...")
        thirty_days_ago = kst_now - timedelta(days=30)
        all_backups = glob.glob(os.path.join(backup_dir, f"{db_name}_backup_*.sql.gz"))
        
        deleted_count = 0
        for f in all_backups:
            try:
                # Extract date from name: dbname_backup_YYYYMMDD_HHMMSS.sql.gz
                basename = os.path.basename(f)
                date_part = basename.split("_backup_")[1].split("_")[0] # YYYYMMDD
                file_date = datetime.strptime(date_part, "%Y%m%d").date()
                
                if file_date < thirty_days_ago.date():
                    os.remove(f)
                    deleted_count += 1
                    print(f"    Deleted old backup: {basename}")
            except Exception as e_del:
                print(f"    Failed to inspect/delete backup {f}: {e_del}")
                
        print(f"  Cleaned up {deleted_count} old backup file(s).")
        return True
        
    except Exception as e:
        print(f"  [ERROR] Exception occurred during DB backup: {e}")
        if os.path.exists(backup_filepath):
            os.remove(backup_filepath)
        return False

if __name__ == "__main__":
    run_backup()
