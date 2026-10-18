import base64
import logging
import time
from typing import Generator
import cv2
import numpy as np
from flask import Blueprint, Response, jsonify, render_template, request

from config import Config
from repositories.student_repository import StudentRepository
from services.auth_service import generate_csrf_token, login_required
from services.face_encoding_service import get_encoding_service
from services.face_recognition_service import FaceRecognitionService

logger = logging.getLogger("attendance.routes.recognition")
recognition_bp = Blueprint("recognition", __name__)

encoding_service = get_encoding_service()
student_repo = StudentRepository()
rec_service = FaceRecognitionService(encoding_service=encoding_service)


def decode_base64_image(base64_str: str) -> np.ndarray:
    """Convert browser data-URL or raw base64 string into BGR OpenCV image."""
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    img_bytes = base64.b64decode(base64_str)
    nparr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)


def generate_error_frame(message: str) -> bytes:
    """Generate an informative placeholder JPEG frame when webcam cannot be accessed."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (30, 30, 40)
    cv2.putText(
        frame,
        "Camera Feed Unavailable",
        (120, 200),
        cv2.FONT_HERSHEY_DUPLEX,
        0.85,
        (0, 100, 255),
        2,
        cv2.LINE_AA
    )
    cv2.putText(
        frame,
        message,
        (60, 260),
        cv2.FONT_HERSHEY_DUPLEX,
        0.50,
        (200, 200, 200),
        1,
        cv2.LINE_AA
    )
    cv2.putText(
        frame,
        "Using browser camera mode instead...",
        (130, 310),
        cv2.FONT_HERSHEY_DUPLEX,
        0.55,
        (100, 220, 100),
        1,
        cv2.LINE_AA
    )
    _, buffer = cv2.imencode(".jpg", frame)
    return buffer.tobytes()


def generate_camera_frames() -> Generator[bytes, None, None]:
    """Capture frames from local webcam, process facial recognition, and yield MJPEG stream."""
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        logger.warning("Local webcam could not be opened on index 0.")
        err_frame = generate_error_frame("Webcam index 0 could not be opened or is in use.")
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + err_frame + b"\r\n")
        return

    # Set camera resolution
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    try:
        while True:
            success, frame = camera.read()
            if not success:
                logger.warning("Failed to grab frame from webcam.")
                time.sleep(0.1)
                continue

            # Process frame with face recognition service
            annotated_frame, _ = rec_service.process_frame(frame)

            # Encode as JPEG
            ret, buffer = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                continue

            frame_bytes = buffer.tobytes()
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
            time.sleep(0.03)  # Limit to ~30 FPS
    except GeneratorExit:
        logger.info("Client disconnected from webcam stream.")
    finally:
        camera.release()
        logger.info("Released webcam hardware device.")


@recognition_bp.route("/recognition")
@login_required
def index():
    registered_students = student_repo.get_all_active_students()
    encodings_loaded, _ = encoding_service.get_registered_encodings()

    return render_template(
        "recognition.html",
        total_active=len(registered_students),
        total_encodings=len(encodings_loaded),
        threshold=rec_service.threshold,
        cooldown=rec_service.cooldown_seconds,
        csrf_token=generate_csrf_token()
    )


@recognition_bp.route("/video_feed")
@login_required
def video_feed():
    """MJPEG stream endpoint for server-attached webcam."""
    return Response(
        generate_camera_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@recognition_bp.route("/api/recognition/process_frame", methods=["POST"])
@login_required
def api_process_frame():
    """API endpoint to process a frame captured directly in the browser via WebRTC."""
    data = request.get_json() or {}
    image_data = data.get("image")
    if not image_data:
        return jsonify({"success": False, "message": "No image payload received."}), 400

    try:
        frame = decode_base64_image(image_data)
        if frame is None:
            return jsonify({"success": False, "message": "Failed to decode image."}), 400

        annotated_frame, detections = rec_service.process_frame(frame)

        # Encode annotated image back to base64 for browser overlay
        _, buffer = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        annotated_base64 = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("utf-8")

        return jsonify({
            "success": True,
            "detections": detections,
            "annotated_image": annotated_base64,
            "timestamp": time.strftime("%H:%M:%S")
        })
    except Exception as e:
        logger.error(f"Error in api_process_frame: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@recognition_bp.route("/api/recognition/latest_event")
@login_required
def api_latest_event():
    """Poll the most recent recognition event."""
    event = rec_service.get_last_event()
    return jsonify({"event": event})
