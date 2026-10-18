import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from config import Config
from repositories.student_repository import StudentRepository
from services.face_engine import BaseFaceEngine, get_face_engine

logger = logging.getLogger("attendance.face_encoding")


class FaceEncodingService:
    """Manages generation, validation, versioned persistence, and safe loading of 128D face encodings."""

    def __init__(
        self,
        student_repo: Optional[StudentRepository] = None,
        face_engine: Optional[BaseFaceEngine] = None,
        encodings_file: Optional[Path] = None,
        dataset_dir: Optional[Path] = None
    ):
        self.student_repo = student_repo or StudentRepository()
        self.face_engine = face_engine or get_face_engine()
        self.encodings_file = encodings_file or Config.ENCODINGS_FILE
        self.dataset_dir = dataset_dir or Config.DATASET_DIR

        # In-memory cached dataset for live matching
        self._cached_data: Optional[Dict[str, Any]] = None
        self._flat_encodings: List[np.ndarray] = []
        self._flat_metadata: List[Dict[str, Any]] = []
        self._last_loaded_mtime: float = 0.0

        # Load encodings if file exists
        self.load_encodings()

    def load_encodings(self) -> bool:
        """Safely load versioned encodings from disk into memory cache."""
        if not self.encodings_file.exists():
            logger.info(f"No existing encodings file found at {self.encodings_file}")
            self._cached_data = None
            self._flat_encodings = []
            self._flat_metadata = []
            self._last_loaded_mtime = 0.0
            return False

        try:
            mtime = self.encodings_file.stat().st_mtime
            with open(self.encodings_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            version = data.get("version", "unknown")
            engine_name = data.get("engine", "unknown")
            logger.info(f"Loading face encodings (Format v{version}, Engine: {engine_name})")

            students = data.get("students", [])
            flat_encs = []
            flat_meta = []

            for s in students:
                student_pk = s.get("id")
                student_code = s.get("student_id")
                name = s.get("name")
                for enc_list in s.get("encodings", []):
                    flat_encs.append(np.array(enc_list, dtype=np.float32))
                    flat_meta.append({
                        "student_pk": student_pk,
                        "student_code": student_code,
                        "name": name
                    })

            self._cached_data = data
            self._flat_encodings = flat_encs
            self._flat_metadata = flat_meta
            self._last_loaded_mtime = mtime
            logger.info(f"Loaded {len(flat_encs)} encodings for {len(students)} registered students.")
            return True
        except Exception as e:
            logger.error(f"Error reading encodings file {self.encodings_file}: {e}")
            self._cached_data = None
            self._flat_encodings = []
            self._flat_metadata = []
            self._last_loaded_mtime = 0.0
            return False

    def get_registered_encodings(self) -> Tuple[List[np.ndarray], List[Dict[str, Any]]]:
        """Retrieve flattened in-memory reference encodings and corresponding student metadata.
        
        Automatically checks disk file modification timestamp to reload encodings if updated.
        """
        if self.encodings_file.exists():
            try:
                disk_mtime = self.encodings_file.stat().st_mtime
                if disk_mtime > self._last_loaded_mtime or len(self._flat_encodings) == 0:
                    self.load_encodings()
            except Exception:
                pass
        return self._flat_encodings, self._flat_metadata

    def build_encodings_for_student(self, student_pk: int, student_id: str) -> List[List[float]]:
        """Process local face images for a single student and extract 128D encodings."""
        clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", student_id.strip())
        student_dir = self.dataset_dir / clean_id
        if not student_dir.exists():
            logger.warning(f"No image dataset directory found for student {student_id} at {student_dir}")
            return []

        image_files = sorted(student_dir.glob("face_*.jpg"))
        if not image_files:
            logger.warning(f"No face images found in {student_dir}")
            return []

        valid_encodings = []
        for img_path in image_files:
            frame = cv2.imread(str(img_path))
            if frame is None or frame.size == 0:
                logger.warning(f"Failed to read image {img_path}")
                continue

            # Detect face and compute encodings
            boxes = self.face_engine.detect_faces(frame)
            if not boxes:
                logger.warning(f"No face detected in saved image {img_path.name}")
                continue

            encs = self.face_engine.compute_encodings(frame, known_face_locations=boxes)
            if encs:
                # Store primary face encoding as float list
                valid_encodings.append(encs[0].tolist())

        logger.info(f"Extracted {len(valid_encodings)} valid encodings from {len(image_files)} images for {student_id}")
        return valid_encodings

    def rebuild_all_encodings(self) -> Dict[str, Any]:
        """Rebuild versioned encodings file from the active database records.
        
        The database is the source of truth: deactivated or deleted students
        are excluded to ensure they can no longer be recognized.
        """
        active_students = self.student_repo.get_all_active_students()
        logger.info(f"Rebuilding biometric encodings for {len(active_students)} active students...")

        student_entries = []
        total_encs = 0

        for student in active_students:
            s_pk = student["id"]
            s_code = student["student_id"]
            s_name = student["full_name"]

            encs = self.build_encodings_for_student(s_pk, s_code)
            if encs:
                student_entries.append({
                    "id": s_pk,
                    "student_id": s_code,
                    "name": s_name,
                    "department": student.get("department"),
                    "encoding_count": len(encs),
                    "encodings": encs
                })
                total_encs += len(encs)

        payload = {
            "version": "1.0",
            "engine": self.face_engine.__class__.__name__,
            "generated_at": datetime.datetime.now().isoformat(),
            "total_students": len(student_entries),
            "total_encodings": total_encs,
            "students": student_entries
        }

        # Safe atomic write to disk
        self.encodings_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.encodings_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(self.encodings_file)

        logger.info(f"Saved {total_encs} encodings across {len(student_entries)} students to {self.encodings_file}")

        # Refresh memory cache
        self.load_encodings()

        return {
            "total_students": len(student_entries),
            "total_encodings": total_encs,
            "engine": payload["engine"],
            "timestamp": payload["generated_at"]
        }


_global_encoding_service: Optional[FaceEncodingService] = None

def get_encoding_service() -> FaceEncodingService:
    global _global_encoding_service
    if _global_encoding_service is None:
        _global_encoding_service = FaceEncodingService()
    return _global_encoding_service
