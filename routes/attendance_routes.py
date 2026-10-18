import datetime
import logging
from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from repositories.student_repository import StudentRepository
from services.attendance_service import AttendanceService
from services.auth_service import generate_csrf_token, login_required, validate_csrf_token

logger = logging.getLogger("attendance.routes.attendance")
attendance_bp = Blueprint("attendance", __name__)

attendance_service = AttendanceService()
student_repo = StudentRepository()


@attendance_bp.route("/attendance")
@login_required
def index():
    page = int(request.args.get("page", 1))
    page_size = 25
    start_date = request.args.get("start_date", "").strip() or None
    end_date = request.args.get("end_date", "").strip() or None
    department = request.args.get("department", "").strip() or None
    source = request.args.get("source", "").strip() or None
    search = request.args.get("search", "").strip() or None

    data = attendance_service.get_attendance_records(
        start_date=start_date,
        end_date=end_date,
        search=search,
        department=department,
        source=source,
        page=page,
        page_size=page_size
    )

    departments = student_repo.get_distinct_departments()
    active_students = student_repo.get_all_active_students()
    today_date, current_time = attendance_service.get_current_date_and_time()

    return render_template(
        "attendance.html",
        records=data["records"],
        total_count=data["total_count"],
        page=data["page"],
        total_pages=data["total_pages"],
        start_date=start_date or "",
        end_date=end_date or "",
        selected_dept=department or "",
        selected_source=source or "",
        search=search or "",
        departments=departments,
        active_students=active_students,
        today_date=today_date,
        current_time=current_time,
        csrf_token=generate_csrf_token()
    )


@attendance_bp.route("/attendance/export")
@login_required
def export_csv():
    start_date = request.args.get("start_date", "").strip() or None
    end_date = request.args.get("end_date", "").strip() or None
    department = request.args.get("department", "").strip() or None
    source = request.args.get("source", "").strip() or None
    search = request.args.get("search", "").strip() or None

    csv_data = attendance_service.export_csv(
        start_date=start_date,
        end_date=end_date,
        search=search,
        department=department,
        source=source
    )

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    filename = f"attendance_records_{today_str}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@attendance_bp.route("/attendance/manual", methods=["POST"])
@login_required
def manual_mark():
    csrf_token = request.form.get("csrf_token")
    if not validate_csrf_token(csrf_token):
        flash("Invalid security token.", "danger")
        return redirect(url_for("attendance.index"))

    student_pk = request.form.get("student_pk")
    attendance_date = request.form.get("attendance_date", "").strip()
    attendance_time = request.form.get("attendance_time", "").strip()

    if not student_pk:
        flash("Please select a valid student.", "danger")
        return redirect(url_for("attendance.index"))

    success, message = attendance_service.mark_manual_attendance(
        student_pk=int(student_pk),
        attendance_date=attendance_date or None,
        attendance_time=attendance_time or None
    )

    if success:
        flash(message, "success")
    else:
        flash(message, "warning")

    return redirect(url_for("attendance.index"))
