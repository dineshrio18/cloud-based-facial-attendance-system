import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from config import Config
from repositories.student_repository import StudentRepository
from services.face_engine import BaseFaceEngine, get_face_engine

logger = logging.getLogger("attendance.face_capture")


class FaceQualityError(Exception):
    """Raised when a captured face frame fails quality or biometric checks."""
    pass


class FaceCaptureService:
    """Handles face image capture, quality validation, and safe dataset storage."""

    def __init__(
        self,
        student_repo: Optional[StudentRepository] = None,
        face_engine: Optional[BaseFaceEngine] = None,
        dataset_dir: Optional[Path] = None
    ):
        self.student_repo = student_repo or StudentRepository()
        self.face_engine = face_engine or get_face_engine()
        self.dataset_dir = dataset_dir or Config.DATASET_DIR
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_student_id(student_id: str) -> str:
        """Sanitize student ID for safe filesystem path construction."""
        cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", student_id.strip())
        if not cleaned:
            raise ValueError("Student ID contains no valid alphanumeric characters.")
        return cleaned

    def validate_frame(
        self,
        frame: np.ndarray,
        last_frame: Optional[np.ndarray] = None
    ) -> Tuple[bool, str, Optional[Tuple[int, int, int, int]]]:
        """Validate quality, illumination, sharpness, and single-subject constraint.
        
        Returns:
            Tuple of (is_valid, message, face_location_box)
        """
        if frame is None or frame.size == 0:
            return False, "Empty or invalid video frame received.", None

        h, w = frame.shape[:2]
        if h < 120 or w < 120:
            return False, f"Frame resolution too low ({w}x{h}). Minimum 120x120 required.", None

        # 1. Face detection & count check
        boxes = self.face_engine.detect_faces(frame)
        if len(boxes) == 0:
            return False, "No face detected. Please position your face clearly in front of the camera.", None
        if len(boxes) > 1:
            return False, "Multiple faces detected. Registration requires a single individual in the frame.", None

        top, right, bottom, left = boxes[0]
        face_w = right - left
        face_h = bottom - top

        # 2. Face size check
        if face_w < 60 or face_h < 60:
            return False, "Face is too far from the camera. Please move closer.", None

        face_crop = frame[max(0, top):min(h, bottom), max(0, left):min(w, right)]
        if face_crop.size == 0:
            return False, "Failed to crop face region.", None

        # 3. Brightness / exposure validation
        gray_face = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if len(face_crop.shape) == 3 else face_crop
        mean_brightness = float(np.mean(gray_face))
        if mean_brightness < 40.0:
            return False, "Lighting is too dark. Please ensure sufficient front lighting.", None
        if mean_brightness > 230.0:
            return False, "Image is overexposed. Please adjust lighting or camera angle.", None

        # 4. Sharpness / blur check (Laplacian variance)
        laplacian_var = float(cv2.Laplacian(gray_face, cv2.CV_64F).var())
        if laplacian_var < 35.0:
            return False, "Face image is blurry. Please hold steady and avoid sudden motion.", None

        # 5. Duplicate frame check against previous saved frame
        if last_frame is not None and last_frame.shape == frame.shape:
            # Measure mean absolute difference
            diff = cv2.absdiff(frame, last_frame)
            mean_diff = float(np.mean(diff))
            if mean_diff < 4.0:
                return False, "Duplicate frame with no variation in pose. Please turn your head slightly.", None

        return True, "Face frame quality validated successfully.", (top, right, bottom, left)

    def get_student_dir(self, student_id: str) -> Path:
        """Get or create safe directory for a student's dataset."""
        safe_id = self.sanitize_student_id(student_id)
        student_dir = self.dataset_dir / safe_id
        student_dir.mkdir(parents=True, exist_ok=True)
        return student_dir

    def save_captured_frame(
        self,
        student_pk: int,
        student_id: str,
        frame: np.ndarray,
        index: int
    ) -> Path:
        """Save validated image to disk and record metadata in database."""
        student_dir = self.get_student_dir(student_id)
        filename = f"face_{index:03d}.jpg"
        file_path = student_dir / filename

        cv2.imwrite(str(file_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        logger.info(f"Saved registration image: {file_path}")

        # Record metadata
        self.student_repo.add_face_image_metadata(
            student_pk=student_pk,
            local_path=str(file_path.relative_to(Config.BASE_DIR)),
            image_status="local_only"
        )
        return file_path

    def get_captured_images_count(self, student_id: str) -> int:
        """Count existing captured images for a student."""
        try:
            student_dir = self.get_student_dir(student_id)
            return len(list(student_dir.glob("face_*.jpg")))
        except Exception:
            return 0
