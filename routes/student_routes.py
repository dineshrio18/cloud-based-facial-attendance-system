import base64
import logging
import shutil
from typing import Optional
import cv2
import numpy as np
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from config import Config
from repositories.student_repository import StudentRepository
from services.auth_service import generate_csrf_token, login_required, validate_csrf_token
from services.face_capture_service import FaceCaptureService
from services.face_encoding_service import get_encoding_service
from services.s3_storage_service import S3StorageService

logger = logging.getLogger("attendance.routes.student")
student_bp = Blueprint("student", __name__)

student_repo = StudentRepository()
capture_service = FaceCaptureService(student_repo=student_repo)
encoding_service = get_encoding_service()
s3_service = S3StorageService(student_repo=student_repo)


def decode_base64_image(base64_str: str) -> Optional[np.ndarray]:
    """Convert browser data-URL or raw base64 string into BGR OpenCV image."""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_bytes = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.error(f"Failed to decode base64 image: {e}")
        return None


@student_bp.route("/students")
@login_required
def list_students():
    page = int(request.args.get("page", 1))
    page_size = 20
    search = request.args.get("search", "").strip() or None
    department = request.args.get("department", "").strip() or None
    status = request.args.get("status", "").strip() or None

    offset = (page - 1) * page_size
    students = student_repo.get_all(status=status, search=search, department=department, offset=offset, limit=page_size)
    total_count = student_repo.count_students(status=status, search=search, department=department)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    departments = student_repo.get_distinct_departments()

    return render_template(
        "students.html",
        students=students,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        search=search or "",
        selected_dept=department or "",
        selected_status=status or "",
        departments=departments,
        csrf_token=generate_csrf_token()
    )


@student_bp.route("/students/register", methods=["GET", "POST"])
@login_required
def register():
    departments = student_repo.get_distinct_departments()

    if request.method == "POST":
        csrf_token = request.form.get("csrf_token")
        if not validate_csrf_token(csrf_token):
            flash("Invalid security token. Please try again.", "danger")
            return redirect(url_for("student.register"))

        student_id = request.form.get("student_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip() or None
        email = request.form.get("email", "").strip() or None
        consent = request.form.get("biometric_consent")

        # Validation
        if not student_id or not full_name:
            flash("Student ID and Full Name are required fields.", "danger")
            return render_template("student_register.html", departments=departments, csrf_token=generate_csrf_token())

        if len(student_id) < 2 or len(student_id) > 40:
            flash("Student ID must be between 2 and 40 characters.", "danger")
            return render_template("student_register.html", departments=departments, csrf_token=generate_csrf_token())

        if not consent:
            flash("You must acknowledge biometric data consent before registering face data.", "danger")
            return render_template("student_register.html", departments=departments, csrf_token=generate_csrf_token())

        # Check unique constraint
        existing = student_repo.get_by_student_id(student_id)
        if existing:
            flash(f"A student with ID '{student_id}' is already registered.", "danger")
            return render_template("student_register.html", departments=departments, csrf_token=generate_csrf_token())

        try:
            student_pk = student_repo.create_student(
                student_id=student_id,
                full_name=full_name,
                department=department,
                email=email,
                status="active"
            )
            flash(f"Student profile created for {full_name} ({student_id}). Please proceed with face capture.", "success")
            return redirect(url_for("student.student_detail", student_pk=student_pk, start_capture=1))
        except Exception as e:
            logger.error(f"Error creating student record: {e}")
            flash(f"Database error creating student: {str(e)}", "danger")

    return render_template("student_register.html", departments=departments, csrf_token=generate_csrf_token())


@student_bp.route("/students/<int:student_pk>")
@login_required
def student_detail(student_pk: int):
    student = student_repo.get_by_id(student_pk)
    if not student:
        flash("Student record not found.", "warning")
        return redirect(url_for("student.list_students"))

    images = student_repo.get_face_images(student_pk)
    from services.attendance_service import AttendanceService
    att_service = AttendanceService()
    history = att_service.get_student_statistics(student_pk)

    start_capture = request.args.get("start_capture", "0") == "1"

    return render_template(
        "student_detail.html",
        student=student,
        images=images,
        history=history,
        start_capture=start_capture,
        target_count=Config.FACE_CAPTURE_TARGET_COUNT,
        csrf_token=generate_csrf_token()
    )


@student_bp.route("/students/<int:student_pk>/edit", methods=["POST"])
@login_required
def edit_student(student_pk: int):
    csrf_token = request.form.get("csrf_token")
    if not validate_csrf_token(csrf_token):
        flash("Invalid security token.", "danger")
        return redirect(url_for("student.student_detail", student_pk=student_pk))

    student = student_repo.get_by_id(student_pk)
    if not student:
        flash("Student record not found.", "warning")
        return redirect(url_for("student.list_students"))

    full_name = request.form.get("full_name", "").strip()
    department = request.form.get("department", "").strip() or None
    email = request.form.get("email", "").strip() or None
    status = request.form.get("status", "active").strip()

    if not full_name:
        flash("Full Name cannot be empty.", "danger")
        return redirect(url_for("student.student_detail", student_pk=student_pk))

    student_repo.update_student(student_pk, full_name, department, email, status)
    flash("Student details updated successfully.", "success")

    # If status changed, rebuild encodings to ensure deactivated students cannot be recognized
    if status != student.get("status"):
        encoding_service.rebuild_all_encodings()
        flash(f"Student marked as {status}. Biometric recognition index refreshed.", "info")

    return redirect(url_for("student.student_detail", student_pk=student_pk))


@student_bp.route("/students/<int:student_pk>/delete", methods=["POST"])
@login_required
def delete_student(student_pk: int):
    csrf_token = request.form.get("csrf_token")
    if not validate_csrf_token(csrf_token):
        flash("Invalid security token.", "danger")
        return redirect(url_for("student.list_students"))

    student = student_repo.get_by_id(student_pk)
    if not student:
        flash("Student record not found.", "warning")
        return redirect(url_for("student.list_students"))

    student_code = student["student_id"]

    # 1. Collect S3 object keys for deletion
    images = student_repo.get_face_images(student_pk)
    s3_keys = [img["object_key"] for img in images if img.get("object_key")]

    # 2. Delete database record (cascades to attendance and face_image_metadata)
    student_repo.delete_student(student_pk)

    # 3. Clean up local dataset folder
    student_dir = capture_service.get_student_dir(student_code)
    if student_dir.exists():
        try:
            shutil.rmtree(student_dir)
            logger.info(f"Removed local dataset directory for {student_code}")
        except Exception as e:
            logger.error(f"Error removing dataset dir: {e}")

    # 4. Clean up S3 images if configured
    if s3_keys:
        s3_service.delete_student_images(student_code, s3_keys)

    # 5. Rebuild encodings
    encoding_service.rebuild_all_encodings()

    flash(f"Student {student['full_name']} ({student_code}) and all biometric data permanently deleted.", "success")
    return redirect(url_for("student.list_students"))


# Interactive Webcam Capture API Endpoints
@student_bp.route("/api/students/validate_frame", methods=["POST"])
@login_required
def api_validate_frame():
    data = request.get_json() or {}
    image_data = data.get("image")
    if not image_data:
        return jsonify({"valid": False, "message": "No image payload received."}), 400

    frame = decode_base64_image(image_data)
    if frame is None:
        return jsonify({"valid": False, "message": "Failed to decode image data."}), 400

    is_valid, msg, box = capture_service.validate_frame(frame)
    return jsonify({
        "valid": is_valid,
        "message": msg,
        "box": list(box) if box else None
    })


@student_bp.route("/api/students/save_frame", methods=["POST"])
@login_required
def api_save_frame():
    data = request.get_json() or {}
    student_pk = data.get("student_pk")
    index = data.get("index", 1)
    image_data = data.get("image")

    if not student_pk or not image_data:
        return jsonify({"success": False, "message": "Missing student_pk or image payload."}), 400

    student = student_repo.get_by_id(int(student_pk))
    if not student:
        return jsonify({"success": False, "message": "Student record not found."}), 404

    frame = decode_base64_image(image_data)
    if frame is None:
        return jsonify({"success": False, "message": "Corrupt image data."}), 400

    try:
        saved_path = capture_service.save_captured_frame(
            student_pk=student["id"],
            student_id=student["student_id"],
            frame=frame,
            index=int(index)
        )
        total_captured = capture_service.get_captured_images_count(student["student_id"])
        return jsonify({
            "success": True,
            "message": "Image saved.",
            "total_captured": total_captured,
            "path": str(saved_path.name)
        })
    except Exception as e:
        logger.error(f"Error saving capture frame: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@student_bp.route("/api/students/finalize_registration", methods=["POST"])
@login_required
def api_finalize_registration():
    data = request.get_json() or {}
    student_pk = data.get("student_pk")
    if not student_pk:
        return jsonify({"success": False, "message": "student_pk required"}), 400

    student = student_repo.get_by_id(int(student_pk))
    if not student:
        return jsonify({"success": False, "message": "Student not found"}), 404

    # Ensure images exist
    count = capture_service.get_captured_images_count(student["student_id"])
    if count == 0:
        return jsonify({
            "success": False,
            "message": "No valid face images have been captured yet. Registration cannot be finalized without face data."
        }), 400

    # 1. Rebuild encodings
    build_result = encoding_service.rebuild_all_encodings()

    # 2. If S3 is configured, trigger upload sync for pending images
    s3_result = None
    if Config.S3_BUCKET_NAME:
        s3_result = s3_service.sync_pending_uploads(batch_size=count + 5)

    return jsonify({
        "success": True,
        "message": f"Biometric enrollment complete. Extracted encodings for {student['full_name']}.",
        "images_captured": count,
        "encodings_total": build_result.get("total_encodings", 0),
        "s3_backup": s3_result
    })
