import logging
from typing import Any, Dict, List, Optional
from services.database_service import DatabaseService, get_db_service

logger = logging.getLogger("attendance.repositories.attendance")


class DuplicateAttendanceError(Exception):
    """Raised when an attendance record already exists for the given student on the specified date."""
    pass


class AttendanceRepository:
    def __init__(self, db_service: Optional[DatabaseService] = None):
        self._db = db_service

    @property
    def db(self) -> DatabaseService:
        if self._db is not None:
            return self._db
        return get_db_service()

    def record_attendance(
        self,
        student_pk: int,
        attendance_date: str,
        attendance_time: str,
        source: str = "facial_recognition"
    ) -> int:
        """Insert attendance record. Enforces unique constraint (student_id, attendance_date).
        
        Raises DuplicateAttendanceError if student is already marked present for the given date.
        """
        sql = """
            INSERT INTO attendance (student_id, attendance_date, attendance_time, source)
            VALUES (%s, %s, %s, %s)
        """
        try:
            return self.db.execute_insert(sql, (student_pk, attendance_date, attendance_time, source))
        except Exception as e:
            err_msg = str(e).lower()
            if "unique" in err_msg or "duplicate" in err_msg or "1062" in err_msg:
                logger.info(f"Duplicate attendance blocked: student_pk={student_pk}, date={attendance_date}")
                raise DuplicateAttendanceError(f"Attendance already marked for student ID {student_pk} on {attendance_date}.")
            raise

    def has_attended_today(self, student_pk: int, attendance_date: str) -> bool:
        """Check whether student has already been marked present today."""
        sql = "SELECT id FROM attendance WHERE student_id = %s AND attendance_date = %s"
        row = self.db.fetch_one(sql, (student_pk, attendance_date))
        return row is not None

    def get_today_attendance(self, attendance_date: str) -> List[Dict[str, Any]]:
        """Retrieve all attendance records for a specific date."""
        sql = """
            SELECT a.id, a.student_id, a.attendance_date, a.attendance_time, a.source, a.created_at,
                   s.student_id as student_code, s.full_name as student_name, s.department, s.email
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            WHERE a.attendance_date = %s
            ORDER BY a.attendance_time DESC, a.id DESC
        """
        return self.db.fetch_all(sql, (attendance_date,))

    def get_records(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        department: Optional[str] = None,
        source: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        conditions = []
        params = []

        if start_date:
            conditions.append("a.attendance_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("a.attendance_date <= %s")
            params.append(end_date)
        if department:
            conditions.append("s.department = %s")
            params.append(department)
        if source:
            conditions.append("a.source = %s")
            params.append(source)
        if search:
            search_param = f"%{search.strip()}%"
            conditions.append("(s.student_id LIKE %s OR s.full_name LIKE %s)")
            params.extend([search_param, search_param])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT a.id, a.student_id, a.attendance_date, a.attendance_time, a.source, a.created_at,
                   s.student_id as student_code, s.full_name as student_name, s.department, s.email
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            {where_clause}
            ORDER BY a.attendance_date DESC, a.attendance_time DESC, a.id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return self.db.fetch_all(sql, tuple(params))

    def count_records(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        department: Optional[str] = None,
        source: Optional[str] = None
    ) -> int:
        conditions = []
        params = []

        if start_date:
            conditions.append("a.attendance_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("a.attendance_date <= %s")
            params.append(end_date)
        if department:
            conditions.append("s.department = %s")
            params.append(department)
        if source:
            conditions.append("a.source = %s")
            params.append(source)
        if search:
            search_param = f"%{search.strip()}%"
            conditions.append("(s.student_id LIKE %s OR s.full_name LIKE %s)")
            params.extend([search_param, search_param])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT COUNT(*) as total
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            {where_clause}
        """
        row = self.db.fetch_one(sql, tuple(params))
        return row["total"] if row else 0

    def get_student_history(
        self,
        student_pk: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conditions = ["a.student_id = %s"]
        params = [student_pk]

        if start_date:
            conditions.append("a.attendance_date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("a.attendance_date <= %s")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(conditions)}"
        sql = f"""
            SELECT a.id, a.student_id, a.attendance_date, a.attendance_time, a.source, a.created_at
            FROM attendance a
            {where_clause}
            ORDER BY a.attendance_date DESC, a.attendance_time DESC
        """
        return self.db.fetch_all(sql, tuple(params))

    def get_dashboard_stats(self, today_date: str) -> Dict[str, Any]:
        """Compute real dashboard statistics from the database.
        
        Calculates total registered active students, today's marked attendance,
        absent count, attendance percentage, and recent 10 records.
        """
        # Total active registered students
        total_students_sql = "SELECT COUNT(*) as total FROM students WHERE status = 'active'"
        total_row = self.db.fetch_one(total_students_sql)
        total_students = total_row["total"] if total_row else 0

        # Attendance marked today (distinct active students)
        marked_today_sql = """
            SELECT COUNT(DISTINCT a.student_id) as total_present
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            WHERE a.attendance_date = %s AND s.status = 'active'
        """
        marked_row = self.db.fetch_one(marked_today_sql, (today_date,))
        marked_today = marked_row["total_present"] if marked_row else 0

        # Unmarked (absent) students today
        unmarked_today = max(0, total_students - marked_today)

        # Percentage
        percentage = round((marked_today / total_students * 100.0), 1) if total_students > 0 else 0.0

        # Recent 10 attendance records
        recent_records = self.get_records(limit=10)

        return {
            "total_students": total_students,
            "marked_today": marked_today,
            "unmarked_today": unmarked_today,
            "attendance_percentage": percentage,
            "recent_records": recent_records,
            "today_date": today_date
        }
