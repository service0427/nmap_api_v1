import pymysql
import os
import sys
from datetime import date

# Ensure core utils are accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import Config
from core.utils import get_kst_date

def fetch_data():
    """
    FSD task synchronization is disabled per user request.
    """
    print("[FSD] Sync is disabled by configuration.")
    return None
