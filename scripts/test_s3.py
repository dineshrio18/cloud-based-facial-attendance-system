# Proxy to verify_s3.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.verify_s3 import test_s3_connection

if __name__ == "__main__":
    success = test_s3_connection()
    sys.exit(0 if success else 1)
