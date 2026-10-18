# Proxy to verify_database.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.verify_database import test_db_connection

if __name__ == "__main__":
    success = test_db_connection()
    sys.exit(0 if success else 1)
