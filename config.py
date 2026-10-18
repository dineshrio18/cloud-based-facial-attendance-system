import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration loaded from environment variables."""

    BASE_DIR = BASE_DIR

    # Application Mode: 'LOCAL' or 'CLOUD'
    APP_MODE = os.getenv("APP_MODE", "LOCAL").upper()
    APP_ENV = os.getenv("APP_ENV", "development").lower()

    # Flask Security & Session
    SECRET_KEY = os.getenv(
        "FLASK_SECRET_KEY",
        "dev-insecure-key-replace-with-a-random-secret-in-production-38295c06"
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set to True when serving over HTTPS in production
    PERMANENT_SESSION_LIFETIME = 28800  # 8 hours in seconds
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max payload

    # Server binding
    HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

    # Local SQLite Database (Used in LOCAL mode)
    LOCAL_DB_PATH = BASE_DIR / os.getenv("LOCAL_DB_PATH", "data/attendance.db")

    # AWS RDS MySQL Configuration (Used in CLOUD mode)
    DB_HOST = os.getenv("DB_HOST", "")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "facial_attendance")
    DB_USER = os.getenv("DB_USER", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
    DB_SSL_CA = os.getenv("DB_SSL_CA", "")

    # AWS S3 Cloud Storage Configuration
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
    AWS_PROFILE = os.getenv("AWS_PROFILE", "default")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")

    # Biometric Recognition Parameters
    RECOGNITION_THRESHOLD = float(os.getenv("RECOGNITION_THRESHOLD", "0.55"))
    AMBIGUITY_MARGIN = float(os.getenv("AMBIGUITY_MARGIN", "0.05"))
    RECOGNITION_COOLDOWN_SECONDS = int(os.getenv("RECOGNITION_COOLDOWN_SECONDS", "60"))
    FACE_CAPTURE_TARGET_COUNT = int(os.getenv("FACE_CAPTURE_TARGET_COUNT", "35"))
    FACE_ENGINE = os.getenv("FACE_ENGINE", "auto")

    # File System Paths
    DATASET_DIR = BASE_DIR / "data" / "dataset"
    ENCODINGS_FILE = BASE_DIR / "encodings" / "face_encodings.json"
    LOGS_DIR = BASE_DIR / "logs"
    LOG_FILE = BASE_DIR / os.getenv("LOG_FILE", "logs/app.log")

    @classmethod
    def is_cloud_mode(cls) -> bool:
        """Return True if application is explicitly running in CLOUD mode."""
        return cls.APP_MODE == "CLOUD"

    @classmethod
    def validate_rds_config(cls) -> tuple[bool, list[str]]:
        """Validate whether RDS MySQL parameters are provided."""
        missing = []
        if not cls.DB_HOST:
            missing.append("DB_HOST")
        if not cls.DB_USER:
            missing.append("DB_USER")
        if not cls.DB_PASSWORD:
            missing.append("DB_PASSWORD")
        if not cls.DB_NAME:
            missing.append("DB_NAME")
        return len(missing) == 0, missing

    @classmethod
    def validate_s3_config(cls) -> tuple[bool, list[str]]:
        """Validate whether S3 bucket parameters are provided."""
        missing = []
        if not cls.S3_BUCKET_NAME:
            missing.append("S3_BUCKET_NAME")
        if not cls.AWS_REGION:
            missing.append("AWS_REGION")
        return len(missing) == 0, missing


class TestingConfig(Config):
    """Configuration for automated test suite execution."""
    TESTING = True
    APP_MODE = "LOCAL"
    LOCAL_DB_PATH = BASE_DIR / "data" / "test_attendance.db"
    ENCODINGS_FILE = BASE_DIR / "encodings" / "test_face_encodings.json"
    SECRET_KEY = "test-secret-key-for-automated-tests"
    WTF_CSRF_ENABLED = False
