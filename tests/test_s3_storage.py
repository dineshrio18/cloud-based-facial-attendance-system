from pathlib import Path
import sys
from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import Config, TestingConfig
from database.init_db import init_sqlite_database
from repositories.student_repository import StudentRepository
from services.database_service import DatabaseService
from services.s3_storage_service import S3StorageService


@pytest.fixture
def s3_test_setup(tmp_path):
    test_db = TestingConfig.LOCAL_DB_PATH
    if test_db.exists():
        test_db.unlink()
    init_sqlite_database(test_db)

    db_service = DatabaseService(TestingConfig)
    student_repo = StudentRepository(db_service)
    s_pk = student_repo.create_student("CS100", "Diana Prince", "Security")

    # Create dummy image on disk
    dummy_img = Config.BASE_DIR / "data" / "dataset" / "CS100" / "face_001.jpg"
    dummy_img.parent.mkdir(parents=True, exist_ok=True)
    with open(dummy_img, "wb") as f:
        f.write(b"fake jpeg image bytes")

    meta_id = student_repo.add_face_image_metadata(
        student_pk=s_pk,
        local_path=str(dummy_img.relative_to(Config.BASE_DIR)),
        image_status="local_only"
    )

    yield student_repo, s_pk, meta_id, dummy_img

    if test_db.exists():
        test_db.unlink()
    if dummy_img.exists():
        dummy_img.unlink()


def test_s3_health_check_unconfigured():
    class EmptyS3Config(TestingConfig):
        S3_BUCKET_NAME = ""

    service = S3StorageService(config=EmptyS3Config)
    health = service.health_check()
    assert health["configured"] is False
    assert health["connected"] is False
    assert "Missing" in health["error"]


def test_s3_upload_success_with_mock(s3_test_setup):
    student_repo, s_pk, meta_id, dummy_img = s3_test_setup

    class MockCloudConfig(TestingConfig):
        S3_BUCKET_NAME = "mock-attendance-bucket"
        AWS_REGION = "us-east-1"

    mock_client = MagicMock()
    mock_client.upload_file.return_value = None  # Successful upload

    service = S3StorageService(config=MockCloudConfig, student_repo=student_repo, s3_client=mock_client)
    success, key, err = service.upload_image(meta_id, "CS100", str(dummy_img.relative_to(Config.BASE_DIR)))

    assert success is True
    assert err is None
    assert key == "students/CS100/face_001.jpg"
    # Ensure boto3 upload was called with AES256 server-side encryption
    mock_client.upload_file.assert_called_once()
    args, kwargs = mock_client.upload_file.call_args
    assert kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"

    # Verify database status updated to 'uploaded'
    imgs = student_repo.get_face_images(s_pk)
    assert imgs[0]["image_status"] == "uploaded"
    assert imgs[0]["object_key"] == key


def test_s3_upload_failure_and_retry_flow(s3_test_setup):
    student_repo, s_pk, meta_id, dummy_img = s3_test_setup

    class MockCloudConfig(TestingConfig):
        S3_BUCKET_NAME = "mock-attendance-bucket"
        AWS_REGION = "us-east-1"

    # Simulate S3 Network or Permission Error
    mock_client = MagicMock()
    mock_client.upload_file.side_effect = Exception("Access Denied (403)")

    service = S3StorageService(config=MockCloudConfig, student_repo=student_repo, s3_client=mock_client)
    success, key, err = service.upload_image(meta_id, "CS100", str(dummy_img.relative_to(Config.BASE_DIR)))

    assert success is False
    assert "Access Denied" in err

    # Status must be recorded as 'upload_failed' in DB
    imgs = student_repo.get_face_images(s_pk)
    assert imgs[0]["image_status"] == "upload_failed"

    # Now simulate recovery and batch retry
    mock_client.upload_file.side_effect = None  # Fixed permissions
    retry_result = service.sync_pending_uploads()
    assert retry_result["total"] == 1
    assert retry_result["succeeded"] == 1
    assert retry_result["failed"] == 0

    # Status updated to uploaded
    imgs_after = student_repo.get_face_images(s_pk)
    assert imgs_after[0]["image_status"] == "uploaded"
