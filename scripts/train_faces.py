import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.face_encoding_service import FaceEncodingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_faces")


def train():
    logger.info("Initializing FaceEncodingService...")
    service = FaceEncodingService()
    result = service.rebuild_all_encodings()

    logger.info("=" * 60)
    logger.info("Biometric Face Model Training & Serialization Completed")
    logger.info(f"Engine:          {result['engine']}")
    logger.info(f"Active Students: {result['total_students']}")
    logger.info(f"Total Encodings: {result['total_encodings']}")
    logger.info(f"Timestamp:       {result['timestamp']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    train()
