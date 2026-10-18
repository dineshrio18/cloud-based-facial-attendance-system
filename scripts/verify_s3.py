import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import Config
from services.s3_storage_service import S3StorageService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_s3")


def test_s3_connection():
    logger.info("=" * 60)
    logger.info("Amazon S3 Cloud Storage Diagnostic")
    logger.info("=" * 60)

    service = S3StorageService()
    health = service.health_check()

    logger.info(f"Bucket Name:  {health['bucket']}")
    logger.info(f"AWS Region:   {health['region']}")
    logger.info(f"Configured:   {health['configured']}")
    logger.info(f"Connected:    {health['connected']}")

    if not health["configured"]:
        logger.warning("\n[Notice] S3 is not configured in .env.")
        logger.warning("To enable Amazon S3 cloud backup:")
        logger.warning("  1. Create a private S3 bucket (e.g. 'my-facial-attendance-bucket').")
        logger.warning("  2. Set S3_BUCKET_NAME and AWS_REGION in .env.")
        logger.warning("  3. Configure credentials via AWS CLI ('aws configure') or IAM role.\n")
        return True

    if not health["connected"]:
        logger.error(f"\n[Error] Could not verify S3 bucket: {health['error']}")
        return False

    logger.info("\n✓ Amazon S3 bucket connectivity and permissions verified successfully!")
    return True


if __name__ == "__main__":
    success = test_s3_connection()
    sys.exit(0 if success else 1)
