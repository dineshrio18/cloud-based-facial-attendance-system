import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import Config
from services.database_service import get_db_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_database")


def test_db_connection():
    db = get_db_service()
    logger.info("=" * 60)
    logger.info(f"Database Health Check: Active Mode [{Config.APP_MODE}]")
    logger.info("=" * 60)

    health = db.health_check()
    logger.info(f"Connected:  {health['connected']}")
    logger.info(f"Target:     {health['target']}")
    logger.info(f"Latency:    {health['latency_ms']} ms")

    if not health["connected"]:
        logger.error(f"Database connection failed: {health['error']}")
        return False

    # Check tables
    tables = ["admin_users", "students", "attendance", "face_image_metadata"]
    logger.info("\nTable Verification:")
    for t in tables:
        try:
            row = db.fetch_one(f"SELECT COUNT(*) as count FROM {t}")
            cnt = row["count"] if row else 0
            logger.info(f"  ✓ Table '{t}': {cnt} records")
        except Exception as e:
            logger.error(f"  ✗ Table '{t}' error: {e}")

    logger.info("\nDatabase verification complete.")
    return True


if __name__ == "__main__":
    success = test_db_connection()
    sys.exit(0 if success else 1)
