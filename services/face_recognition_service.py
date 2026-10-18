import datetime
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from config import Config
from services.attendance_service import AttendanceService
from services.face_encoding_service import FaceEncodingService
from services.face_engine import BaseFaceEngine, get_face_engine

logger = logging.getLogger("attendance.recognition")


class FaceRecognitionService:
    """Real-time webcam recognition engine with distance thresholding and duplicate-safe attendance."""

    def __init__(
        self,
        encoding_service: Optional[FaceEncodingService] = None,
        attendance_service: Optional[AttendanceService] = None,
        face_engine: Optional[BaseFaceEngine] = None,
        threshold: Optional[float] = None,
        ambiguity_margin: Optional[float] = None,
        cooldown_seconds: Optional[int] = None
    ):
        self.encoding_service = encoding_service or FaceEncodingService()
        self.attendance_service = attendance_service or AttendanceService()
        self.face_engine = face_engine or get_face_engine()

        self.threshold = threshold if threshold is not None else Config.RECOGNITION_THRESHOLD
        self.ambiguity_margin = ambiguity_margin if ambiguity_margin is not None else Config.AMBIGUITY_MARGIN
        self.cooldown_seconds = cooldown_seconds if cooldown_seconds is not None else Config.RECOGNITION_COOLDOWN_SECONDS

        # In-memory cooldown tracking {student_pk: last_recognized_epoch_timestamp}
        self._cooldown_lock = threading.Lock()
        self._cooldown_tracker: Dict[int, float] = {}

        # Last detected recognition event for dashboard / UI live feed
        self._last_event: Optional[Dict[str, Any]] = None

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Analyze frame, detect faces, perform thresholded identity matching, and annotate."""
        if frame is None or frame.size == 0:
            return frame, []

        annotated = frame.copy()
        h, w = frame.shape[:2]

        # 1. Detect all face locations
        face_boxes = self.face_engine.detect_faces(frame)
        if not face_boxes:
            return annotated, []

        # 2. Extract 128D encodings
        encodings = self.face_engine.compute_encodings(frame, known_face_locations=face_boxes)
        if not encodings:
            return annotated, []

        # 3. Retrieve registered encodings
        known_encs, known_meta = self.encoding_service.get_registered_encodings()

        detection_results = []
        now_ts = time.time()

        for idx, (box, enc) in enumerate(zip(face_boxes, encodings)):
            top, right, bottom, left = box
            
            # Boundary checks
            top = max(0, min(h - 1, top))
            bottom = max(0, min(h, bottom))
            left = max(0, min(w - 1, left))
            right = max(0, min(w, right))

            # Match against registered encodings
            best_idx, best_dist, is_ambiguous = self.face_engine.find_best_match(
                known_encs,
                enc,
                threshold=self.threshold,
                ambiguity_margin=self.ambiguity_margin,
                known_metadata=known_meta
            )

            if best_idx is not None and not is_ambiguous:
                # Registered student identified
                match_meta = known_meta[best_idx]
                student_pk = match_meta["student_pk"]
                student_code = match_meta["student_code"]
                student_name = match_meta["name"]

                confidence = max(0.0, min(100.0, round((1.0 - (best_dist / self.threshold)) * 100.0, 1)))

                # Check session cooldown before recording attendance
                attendance_status = "cooldown"
                attendance_message = "Recognition cooldown active."
                with self._cooldown_lock:
                    last_time = self._cooldown_tracker.get(student_pk, 0.0)
                    if (now_ts - last_time) >= self.cooldown_seconds:
                        self._cooldown_tracker[student_pk] = now_ts
                        # Attempt to mark attendance
                        att_res = self.attendance_service.mark_face_attendance(
                            student_pk=student_pk,
                            student_code=student_code,
                            student_name=student_name
                        )
                        attendance_status = att_res.get("status", "unknown")
                        attendance_message = att_res.get("message", "")
                        self._last_event = {
                            "student_id": student_code,
                            "name": student_name,
                            "distance": round(best_dist, 4),
                            "confidence": confidence,
                            "status": attendance_status,
                            "message": attendance_message,
                            "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                        }

                # Visual bounding box: GREEN for recognized student
                box_color = (0, 200, 0)
                label = f"{student_name} ({student_code})"
                sub_label = f"Dist: {best_dist:.3f} | Conf: {confidence:.0f}%"

                detection_results.append({
                    "recognized": True,
                    "student_pk": student_pk,
                    "student_id": student_code,
                    "name": student_name,
                    "distance": round(best_dist, 4),
                    "confidence": confidence,
                    "attendance_status": attendance_status,
                    "attendance_message": attendance_message,
                    "box": [int(top), int(right), int(bottom), int(left)]
                })
            else:
                # UNKNOWN face (or ambiguous match)
                box_color = (0, 0, 220)  # RED
                label = "Unknown Person"
                sub_label = f"Distance: {best_dist:.3f} (> {self.threshold:.2f})"

                detection_results.append({
                    "recognized": False,
                    "student_id": None,
                    "name": "Unknown",
                    "distance": round(best_dist, 4) if best_idx is not None else None,
                    "confidence": 0.0,
                    "attendance_status": "none",
                    "box": [int(top), int(right), int(bottom), int(left)]
                })

            # Draw aesthetic bounding box with corner brackets
            self._draw_aesthetic_box(annotated, left, top, right, bottom, box_color, label, sub_label)

        return annotated, detection_results

    def _draw_aesthetic_box(
        self,
        img: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: Tuple[int, int, int],
        primary_text: str,
        secondary_text: str
    ):
        """Render modern corner-accented bounding boxes and readable labels."""
        # Main rectangle
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

        # Corner accents
        line_len = max(10, min(25, (x2 - x1) // 4))
        # Top-left
        cv2.line(img, (x1, y1), (x1 + line_len, y1), color, 4)
        cv2.line(img, (x1, y1), (x1, y1 + line_len), color, 4)
        # Top-right
        cv2.line(img, (x2, y1), (x2 - line_len, y1), color, 4)
        cv2.line(img, (x2, y1), (x2, y1 + line_len), color, 4)
        # Bottom-left
        cv2.line(img, (x1, y2), (x1 + line_len, y2), color, 4)
        cv2.line(img, (x1, y2), (x1, y2 - line_len), color, 4)
        # Bottom-right
        cv2.line(img, (x2, y2), (x2 - line_len, y2), color, 4)
        cv2.line(img, (x2, y2), (x2, y2 - line_len), color, 4)

        # Background header for text
        header_h = 42
        cv2.rectangle(img, (x1, max(0, y1 - header_h)), (x2, y1), color, -1)
        # Primary label
        cv2.putText(
            img,
            primary_text,
            (x1 + 6, max(14, y1 - 22)),
            cv2.FONT_HERSHEY_DUPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )
        # Secondary subtitle
        cv2.putText(
            img,
            secondary_text,
            (x1 + 6, max(28, y1 - 6)),
            cv2.FONT_HERSHEY_DUPLEX,
            0.40,
            (240, 240, 240),
            1,
            cv2.LINE_AA
        )

    def get_last_event(self) -> Optional[Dict[str, Any]]:
        """Return the most recent recognition event details."""
        return self._last_event
