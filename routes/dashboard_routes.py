import logging
from flask import Blueprint, jsonify, render_template

from config import Config
from services.attendance_service import AttendanceService
from services.auth_service import login_required
from services.database_service import get_db_service
from services.s3_storage_service import S3StorageService

logger = logging.getLogger("attendance.routes.dashboard")
dashboard_bp = Blueprint("dashboard", __name__)

attendance_service = AttendanceService()
s3_service = S3StorageService()
db_service = get_db_service()


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
def index():
    summary = attendance_service.get_dashboard_summary()
    db_health = db_service.health_check()
    s3_health = s3_service.health_check()

    return render_template(
        "dashboard.html",
        stats=summary,
        db_health=db_health,
        s3_health=s3_health,
        app_mode=Config.APP_MODE,
        today_date=summary["today_date"]
    )


@dashboard_bp.route("/api/status")
@login_required
def status_api():
    summary = attendance_service.get_dashboard_summary()
    db_health = db_service.health_check()
    s3_health = s3_service.health_check()

    return jsonify({
        "mode": Config.APP_MODE,
        "database": db_health,
        "s3": s3_health,
        "total_students": summary["total_students"],
        "marked_today": summary["marked_today"],
        "attendance_percentage": summary["attendance_percentage"]
    })
