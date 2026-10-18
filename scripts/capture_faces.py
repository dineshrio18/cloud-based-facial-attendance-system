import argparse
import logging
import sys
import time
from pathlib import Path
import cv2

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import Config
from repositories.student_repository import StudentRepository
from services.face_capture_service import FaceCaptureService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("capture_faces")


def capture_student_faces(student_id: str, target_count: int = 35):
    """CLI tool to capture 30-50 face samples directly via local webcam."""
    student_repo = StudentRepository()
    student = student_repo.get_by_student_id(student_id)
    if not student:
        logger.error(f"Student '{student_id}' does not exist in database. Please register the student profile first.")
        return False

    capture_service = FaceCaptureService(student_repo=student_repo)
    student_pk = student["id"]

    logger.info(f"Opening camera to capture {target_count} face samples for {student['full_name']} ({student_id})...")
    logger.info("Press 'q' or ESC in the preview window to cancel.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Webcam device could not be opened. Check connection and permissions.")
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    saved_count = capture_service.get_captured_images_count(student_id)
    last_saved_frame = None

    try:
        while saved_count < target_count:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            display_frame = frame.copy()
            is_valid, msg, box = capture_service.validate_frame(frame, last_frame=last_saved_frame)

            color = (0, 200, 0) if is_valid else (0, 0, 220)
            if box:
                t, r, b, l = box
                cv2.rectangle(display_frame, (l, t), (r, b), color, 2)

            # Overlay status text
            cv2.putText(
                display_frame,
                f"Samples: {saved_count}/{target_count} | {msg}",
                (20, 30),
                cv2.FONT_HERSHEY_DUPLEX,
                0.55,
                color,
                1,
                cv2.LINE_AA
            )

            cv2.imshow(f"Facial Enrollment - {student['full_name']}", display_frame)

            if is_valid:
                saved_count += 1
                capture_service.save_captured_frame(student_pk, student_id, frame, saved_count)
                last_saved_frame = frame.copy()
                logger.info(f"Captured [{saved_count}/{target_count}] - {msg}")
                time.sleep(0.3)  # Brief pause between samples

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                logger.info("Capture cancelled by operator.")
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    logger.info(f"Capture session finished. Total samples recorded: {saved_count}")
    return saved_count >= target_count


def main():
    parser = argparse.ArgumentParser(description="Capture face samples for a registered student via webcam.")
    parser.add_argument("--student-id", required=True, help="Institutional student ID (e.g. CS2026001)")
    parser.add_argument("--count", type=int, default=35, help="Number of face samples to capture (default: 35)")
    args = parser.parse_args()

    capture_student_faces(args.student_id, args.count)


if __name__ == "__main__":
    main()
