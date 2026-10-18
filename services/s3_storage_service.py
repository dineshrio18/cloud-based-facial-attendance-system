import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import Config
from repositories.student_repository import StudentRepository

logger = logging.getLogger("attendance.s3")


class S3StorageService:
    """Manages secure, private, server-side encrypted storage of biometric face images in Amazon S3."""

    def __init__(
        self,
        config=None,
        student_repo: Optional[StudentRepository] = None,
        s3_client: Optional[Any] = None
    ):
        self.config = config or Config
        self.student_repo = student_repo or StudentRepository()
        self._client = s3_client
        self.bucket_name = self.config.S3_BUCKET_NAME
        self.region = self.config.AWS_REGION

    def get_client(self):
        """Retrieve or create an authorized boto3 S3 client using environment or AWS profiles."""
        if self._client is not None:
            return self._client

        # Prioritize explicit credentials if supplied, otherwise standard AWS credential chain
        session_kwargs = {}
        if self.config.AWS_REGION:
            session_kwargs["region_name"] = self.config.AWS_REGION

        if self.config.AWS_ACCESS_KEY_ID and self.config.AWS_SECRET_ACCESS_KEY:
            os.environ.pop("AWS_PROFILE", None)
            session_kwargs["aws_access_key_id"] = self.config.AWS_ACCESS_KEY_ID
            session_kwargs["aws_secret_access_key"] = self.config.AWS_SECRET_ACCESS_KEY
            session = boto3.Session(**session_kwargs)
            self._client = session.client("s3")
            return self._client
        elif self.config.AWS_PROFILE:
            try:
                session = boto3.Session(profile_name=self.config.AWS_PROFILE, **session_kwargs)
                self._client = session.client("s3")
                return self._client
            except Exception as e:
                logger.debug(f"AWS named profile '{self.config.AWS_PROFILE}' not found or default: {e}")

        session = boto3.Session(**session_kwargs)
        self._client = session.client("s3")
        return self._client

    def health_check(self) -> Dict[str, Any]:
        """Perform an active connectivity and permission test against the configured S3 bucket."""
        valid, missing = self.config.validate_s3_config()
        if not valid:
            return {
                "configured": False,
                "connected": False,
                "bucket": self.bucket_name or "Not configured",
                "region": self.region,
                "error": f"Missing environment configuration: {', '.join(missing)}"
            }

        try:
            client = self.get_client()
            # head_bucket checks bucket existence and caller read permissions
            client.head_bucket(Bucket=self.bucket_name)
            return {
                "configured": True,
                "connected": True,
                "bucket": self.bucket_name,
                "region": self.region,
                "error": None
            }
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            msg = e.response.get("Error", {}).get("Message", str(e))
            logger.warning(f"S3 health check ClientError ({code}): {msg}")
            return {
                "configured": True,
                "connected": False,
                "bucket": self.bucket_name,
                "region": self.region,
                "error": f"[{code}] {msg}"
            }
        except (BotoCoreError, Exception) as e:
            logger.error(f"S3 health check connection error: {e}")
            return {
                "configured": True,
                "connected": False,
                "bucket": self.bucket_name,
                "region": self.region,
                "error": str(e)
            }

    def generate_object_key(self, student_code: str, local_file_name: str) -> str:
        """Generate safe, organized, non-conflicting S3 object key."""
        clean_code = student_code.strip().replace(" ", "_")
        return f"students/{clean_code}/{local_file_name}"

    def upload_image(
        self,
        image_metadata_id: int,
        student_code: str,
        local_path_str: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Upload a local face image to private S3 bucket with SSE-S3 encryption.
        
        Returns:
            Tuple of (success, object_key or None, error_message or None)
        """
        valid, missing = self.config.validate_s3_config()
        if not valid:
            err = f"S3 configuration incomplete: missing {', '.join(missing)}"
            self.student_repo.update_image_status(image_metadata_id, "upload_failed")
            return False, None, err

        local_full_path = Config.BASE_DIR / local_path_str
        if not local_full_path.exists():
            err = f"Local image file not found at {local_full_path}"
            self.student_repo.update_image_status(image_metadata_id, "upload_failed")
            return False, None, err

        object_key = self.generate_object_key(student_code, local_full_path.name)

        try:
            client = self.get_client()
            # Upload with SSE-S3 (AES256) server-side encryption and private ACL
            client.upload_file(
                Filename=str(local_full_path),
                Bucket=self.bucket_name,
                Key=object_key,
                ExtraArgs={
                    "ServerSideEncryption": "AES256",
                    "ContentType": "image/jpeg"
                }
            )
            # Update database record
            self.student_repo.update_image_status(image_metadata_id, "uploaded", object_key)
            logger.info(f"Successfully uploaded {local_path_str} to s3://{self.bucket_name}/{object_key}")
            return True, object_key, None
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Failed to upload {local_path_str} to S3: {err_msg}")
            self.student_repo.update_image_status(image_metadata_id, "upload_failed")
            return False, None, err_msg

    def sync_pending_uploads(self, batch_size: int = 25) -> Dict[str, Any]:
        """Process images that are pending or previously failed S3 upload."""
        pending = self.student_repo.get_pending_s3_uploads(limit=batch_size)
        if not pending:
            return {"total": 0, "succeeded": 0, "failed": 0, "errors": []}

        succeeded = 0
        failed = 0
        errors = []

        for item in pending:
            image_id = item["id"]
            student_code = item["student_code"]
            local_path = item["local_path"]

            success, key, err = self.upload_image(image_id, student_code, local_path)
            if success:
                succeeded += 1
            else:
                failed += 1
                errors.append(f"{local_path}: {err}")

        return {
            "total": len(pending),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors
        }

    def delete_student_images(self, student_code: str, object_keys: List[str]) -> Tuple[int, int]:
        """Delete student image objects from S3 upon authorized student deletion."""
        if not self.config.S3_BUCKET_NAME or not object_keys:
            return 0, 0

        valid_keys = [{"Key": k} for k in object_keys if k]
        if not valid_keys:
            return 0, 0

        try:
            client = self.get_client()
            response = client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": valid_keys, "Quiet": True}
            )
            deleted_count = len(response.get("Deleted", []))
            errors_count = len(response.get("Errors", []))
            logger.info(f"Deleted {deleted_count} S3 objects for student {student_code}")
            return deleted_count, errors_count
        except Exception as e:
            logger.error(f"Failed to delete S3 objects for student {student_code}: {e}")
            return 0, len(valid_keys)
