import csv
import datetime
import io
import logging
from typing import Any, Dict, List, Optional, Tuple
import pytz

from config import Config
from repositories.attendance_repository import AttendanceRepository, DuplicateAttendanceError
from repositories.student_repository import StudentRepository

logger = logging.getLogger("attendance.service")


class AttendanceService:
    """Core business logic for recording, querying, and exporting attendance."""

    def __init__(
        self,
        attendance_repo: Optional[AttendanceRepository] = None,
        student_repo: Optional[StudentRepository] = None,
        timezone_str: Optional[str] = None
    ):
        self.attendance_repo = attendance_repo or AttendanceRepository()
        self.student_repo = student_repo or StudentRepository()
        self.tz_name = timezone_str or Config.TIMEZONE
        try:
            self.tz = pytz.timezone(self.tz_name)
        except Exception:
            self.tz = pytz.UTC

    def get_current_date_and_time(self) -> Tuple[str, str]:
        """Obtain current server date and time according to configured timezone."""
        now = datetime.datetime.now(self.tz)
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

    def mark_face_attendance(
        self,
        student_pk: int,
        student_code: str,
        student_name: str
    ) -> Dict[str, Any]:
        """Record attendance from live facial recognition.
        
        Guarantees that repeated frames within the same session or day do not create
        duplicate attendance records.
        """
        today_date, current_time = self.get_current_date_and_time()

        # Fast pre-check
        if self.attendance_repo.has_attended_today(student_pk, today_date):
            return {
                "success": False,
                "status": "already_marked",
                "message": f"{student_name} ({student_code}) has already been marked present today.",
                "student_id": student_code,
                "student_name": student_name,
                "date": today_date,
                "time": current_time
            }

        # Database-enforced atomic write with unique constraint handling
        try:
            record_id = self.attendance_repo.record_attendance(
                student_pk=student_pk,
                attendance_date=today_date,
                attendance_time=current_time,
                source="facial_recognition"
            )
            logger.info(f"Marked facial attendance for {student_name} ({student_code}) at {current_time}")
            return {
                "success": True,
                "status": "marked",
                "message": f"Attendance recorded for {student_name} ({student_code}) at {current_time}.",
                "record_id": record_id,
                "student_id": student_code,
                "student_name": student_name,
                "date": today_date,
                "time": current_time
            }
        except DuplicateAttendanceError:
            return {
                "success": False,
                "status": "already_marked",
                "message": f"{student_name} ({student_code}) was already recorded for {today_date}.",
                "student_id": student_code,
                "student_name": student_name,
                "date": today_date,
                "time": current_time
            }
        except Exception as e:
            logger.error(f"Error marking facial attendance for student_pk {student_pk}: {e}")
            return {
                "success": False,
                "status": "error",
                "message": f"Database error while recording attendance: {str(e)}"
            }

    def mark_manual_attendance(
        self,
        student_pk: int,
        attendance_date: Optional[str] = None,
        attendance_time: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Allow administrative manual attendance entry for authorized operators."""
        today_date, current_time = self.get_current_date_and_time()
        date_to_mark = attendance_date.strip() if attendance_date else today_date
        time_to_mark = attendance_time.strip() if attendance_time else current_time

        student = self.student_repo.get_by_id(student_pk)
        if not student:
            return False, "Student not found."

        try:
            self.attendance_repo.record_attendance(
                student_pk=student_pk,
                attendance_date=date_to_mark,
                attendance_time=time_to_mark,
                source="manual"
            )
            logger.info(f"Manual attendance recorded for {student['full_name']} ({student['student_id']}) on {date_to_mark}")
            return True, f"Manual attendance recorded for {student['full_name']} on {date_to_mark}."
        except DuplicateAttendanceError:
            return False, f"Attendance record already exists for {student['full_name']} on {date_to_mark}."
        except Exception as e:
            logger.error(f"Failed to record manual attendance: {e}")
            return False, f"Database error: {str(e)}"

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Fetch dashboard statistics for today."""
        today_date, _ = self.get_current_date_and_time()
        return self.attendance_repo.get_dashboard_stats(today_date)

    def get_attendance_records(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        department: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Query paginated attendance records with optional filtering."""
        offset = max(0, (page - 1) * page_size)
        records = self.attendance_repo.get_records(
            start_date=start_date,
            end_date=end_date,
            search=search,
            department=department,
            source=source,
            offset=offset,
            limit=page_size
        )
        total_count = self.attendance_repo.count_records(
            start_date=start_date,
            end_date=end_date,
            search=search,
            department=department,
            source=source
        )
        total_pages = max(1, (total_count + page_size - 1) // page_size)

        return {
            "records": records,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    def get_student_statistics(
        self,
        student_pk: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate historical attendance records and percentage for a student."""
        records = self.attendance_repo.get_student_history(student_pk, start_date, end_date)
        student = self.student_repo.get_by_id(student_pk)
        return {
            "student": student,
            "total_attended_days": len(records),
            "records": records
        }

    def export_csv(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        department: Optional[str] = None,
        source: Optional[str] = None
    ) -> str:
        """Generate CSV string of attendance records for auditing and reporting."""
        records = self.attendance_repo.get_records(
            start_date=start_date,
            end_date=end_date,
            search=search,
            department=department,
            source=source,
            offset=0,
            limit=100000
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Record ID", "Student ID", "Full Name", "Department", "Email", "Date", "Time", "Source"])

        for r in records:
            writer.writerow([
                r.get("id"),
                r.get("student_code", ""),
                r.get("student_name", ""),
                r.get("department", "") or "",
                r.get("email", "") or "",
                r.get("attendance_date", ""),
                r.get("attendance_time", ""),
                r.get("source", "")
            ])

        return output.getvalue()
