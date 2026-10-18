import logging
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from config import Config
from repositories.student_repository import StudentRepository
from services.auth_service import AuthService, generate_csrf_token, login_required, validate_csrf_token
from services.database_service import get_db_service
from services.face_encoding_service import FaceEncodingService
from services.s3_storage_service import S3StorageService

logger = logging.getLogger("attendance.routes.settings")
settings_bp = Blueprint("settings", __name__)

auth_service = AuthService()
db_service = get_db_service()
s3_service = S3StorageService()
encoding_service = FaceEncodingService()
student_repo = StudentRepository()


@settings_bp.route("/settings")
@login_required
def index():
    db_health = db_service.health_check()
    s3_health = s3_service.health_check()

    pending_s3 = student_repo.get_pending_s3_uploads(limit=100)
    encodings_loaded, _ = encoding_service.get_registered_encodings()

    return render_template(
        "settings.html",
        config=Config,
        db_health=db_health,
        s3_health=s3_health,
        pending_s3_count=len(pending_s3),
        total_encodings=len(encodings_loaded),
        csrf_token=generate_csrf_token()
    )


@settings_bp.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    csrf_token = request.form.get("csrf_token")
    if not validate_csrf_token(csrf_token):
        flash("Invalid security token.", "danger")
        return redirect(url_for("settings.index"))

    current_user_id = session.get("user_id")
    old_pw = request.form.get("current_password", "").strip()
    new_pw = request.form.get("new_password", "").strip()
    confirm_pw = request.form.get("confirm_password", "").strip()

    if new_pw != confirm_pw:
        flash("New password and confirmation do not match.", "danger")
        return redirect(url_for("settings.index"))

    success, msg = auth_service.change_password(current_user_id, old_pw, new_pw)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")

    return redirect(url_for("settings.index"))


@settings_bp.route("/settings/rebuild_encodings", methods=["POST"])
@login_required
def rebuild_encodings():
    csrf_token = request.form.get("csrf_token")
    if not validate_csrf_token(csrf_token):
        flash("Invalid security token.", "danger")
        return redirect(url_for("settings.index"))

    try:
        result = encoding_service.rebuild_all_encodings()
        flash(
            f"Biometric encodings rebuilt successfully. Processed {result['total_encodings']} face encodings "
            f"across {result['total_students']} active students.",
            "success"
        )
    except Exception as e:
        logger.error(f"Error rebuilding encodings: {e}")
        flash(f"Failed to rebuild encodings: {str(e)}", "danger")

    return redirect(url_for("settings.index"))


@settings_bp.route("/settings/s3_sync", methods=["POST"])
@login_required
def s3_sync():
    csrf_token = request.form.get("csrf_token")
    if not validate_csrf_token(csrf_token):
        flash("Invalid security token.", "danger")
        return redirect(url_for("settings.index"))

    valid, missing = Config.validate_s3_config()
    if not valid:
        flash(f"Cannot sync with S3. Missing configuration variables: {', '.join(missing)}", "warning")
        return redirect(url_for("settings.index"))

    result = s3_service.sync_pending_uploads(batch_size=50)
    if result["total"] == 0:
        flash("No pending images to upload. All images are already backed up in S3.", "info")
    elif result["failed"] == 0:
        flash(f"Successfully uploaded {result['succeeded']} pending images to S3.", "success")
    else:
        flash(
            f"Uploaded {result['succeeded']} images, but {result['failed']} failed. Check application logs.",
            "warning"
        )

    return redirect(url_for("settings.index"))
