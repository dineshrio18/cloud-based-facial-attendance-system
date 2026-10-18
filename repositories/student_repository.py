import logging
from typing import Any, Dict, List, Optional
from services.database_service import DatabaseService, get_db_service

logger = logging.getLogger("attendance.repositories.student")


class StudentRepository:
    def __init__(self, db_service: Optional[DatabaseService] = None):
        self._db = db_service

    @property
    def db(self) -> DatabaseService:
        if self._db is not None:
            return self._db
        return get_db_service()

    def get_by_id(self, student_pk: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM students WHERE id = %s"
        return self.db.fetch_one(sql, (student_pk,))

    def get_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM students WHERE student_id = %s"
        return self.db.fetch_one(sql, (student_id.strip(),))

    def create_student(
        self,
        student_id: str,
        full_name: str,
        department: Optional[str] = None,
        email: Optional[str] = None,
        status: str = "active"
    ) -> int:
        sql = """
            INSERT INTO students (student_id, full_name, department, email, status)
            VALUES (%s, %s, %s, %s, %s)
        """
        return self.db.execute_insert(
            sql,
            (student_id.strip(), full_name.strip(), department.strip() if department else None, email.strip() if email else None, status)
        )

    def update_student(
        self,
        student_pk: int,
        full_name: str,
        department: Optional[str] = None,
        email: Optional[str] = None,
        status: str = "active"
    ) -> bool:
        sql = """
            UPDATE students
            SET full_name = %s, department = %s, email = %s, status = %s
            WHERE id = %s
        """
        rows = self.db.execute_query(
            sql,
            (full_name.strip(), department.strip() if department else None, email.strip() if email else None, status, student_pk)
        )
        return rows > 0

    def delete_student(self, student_pk: int) -> bool:
        """Permanently delete a student and cascading foreign records (attendance, image metadata)."""
        sql = "DELETE FROM students WHERE id = %s"
        rows = self.db.execute_query(sql, (student_pk,))
        return rows > 0

    def set_status(self, student_pk: int, status: str) -> bool:
        """Deactivate or activate student."""
        sql = "UPDATE students SET status = %s WHERE id = %s"
        return self.db.execute_query(sql, (status, student_pk)) > 0

    def get_all(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        department: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        conditions = []
        params = []

        if status:
            conditions.append("status = %s")
            params.append(status)
        if department:
            conditions.append("department = %s")
            params.append(department)
        if search:
            search_param = f"%{search.strip()}%"
            conditions.append("(student_id LIKE %s OR full_name LIKE %s OR email LIKE %s)")
            params.extend([search_param, search_param, search_param])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT s.*, 
                   (SELECT COUNT(*) FROM face_image_metadata fim WHERE fim.student_id = s.id) as image_count,
                   (SELECT COUNT(*) FROM attendance a WHERE a.student_id = s.id) as total_attendance
            FROM students s
            {where_clause}
            ORDER BY s.id DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        return self.db.fetch_all(sql, tuple(params))

    def count_students(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        department: Optional[str] = None
    ) -> int:
        conditions = []
        params = []

        if status:
            conditions.append("status = %s")
            params.append(status)
        if department:
            conditions.append("department = %s")
            params.append(department)
        if search:
            search_param = f"%{search.strip()}%"
            conditions.append("(student_id LIKE %s OR full_name LIKE %s OR email LIKE %s)")
            params.extend([search_param, search_param, search_param])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT COUNT(*) as total FROM students {where_clause}"
        row = self.db.fetch_one(sql, tuple(params))
        return row["total"] if row else 0

    def get_all_active_students(self) -> List[Dict[str, Any]]:
        sql = "SELECT id, student_id, full_name, department, email FROM students WHERE status = 'active' ORDER BY full_name ASC"
        return self.db.fetch_all(sql)

    def get_distinct_departments(self) -> List[str]:
        sql = "SELECT DISTINCT department FROM students WHERE department IS NOT NULL AND department != '' ORDER BY department ASC"
        rows = self.db.fetch_all(sql)
        return [r["department"] for r in rows]

    # Face image metadata methods
    def add_face_image_metadata(
        self,
        student_pk: int,
        local_path: str,
        object_key: Optional[str] = None,
        image_status: str = "local_only"
    ) -> int:
        sql = """
            INSERT INTO face_image_metadata (student_id, object_key, local_path, image_status)
            VALUES (%s, %s, %s, %s)
        """
        return self.db.execute_insert(sql, (student_pk, object_key, local_path, image_status))

    def get_face_images(self, student_pk: int) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM face_image_metadata WHERE student_id = %s ORDER BY id ASC"
        return self.db.fetch_all(sql, (student_pk,))

    def update_image_status(self, image_id: int, image_status: str, object_key: Optional[str] = None) -> bool:
        if object_key:
            sql = "UPDATE face_image_metadata SET image_status = %s, object_key = %s WHERE id = %s"
            params = (image_status, object_key, image_id)
        else:
            sql = "UPDATE face_image_metadata SET image_status = %s WHERE id = %s"
            params = (image_status, image_id)
        return self.db.execute_query(sql, params) > 0

    def get_pending_s3_uploads(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve images that have not been successfully uploaded to S3."""
        sql = """
            SELECT fim.*, s.student_id as student_code, s.full_name
            FROM face_image_metadata fim
            JOIN students s ON s.id = fim.student_id
            WHERE fim.image_status IN ('local_only', 'upload_failed')
            ORDER BY fim.id ASC
            LIMIT %s
        """
        return self.db.fetch_all(sql, (limit,))
