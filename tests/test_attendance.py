import pytest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import TestingConfig
from database.init_db import init_sqlite_database
from repositories.attendance_repository import AttendanceRepository, DuplicateAttendanceError
from repositories.student_repository import StudentRepository
from services.attendance_service import AttendanceService
from services.database_service import DatabaseService


@pytest.fixture
def attendance_setup():
    test_db = TestingConfig.LOCAL_DB_PATH
    if test_db.exists():
        test_db.unlink()
    init_sqlite_database(test_db)

    db_service = DatabaseService(TestingConfig)
    student_repo = StudentRepository(db_service)
    att_repo = AttendanceRepository(db_service)
    service = AttendanceService(att_repo, student_repo)

    # Seed students
    s1_pk = student_repo.create_student("CS001", "Emma Watson", "Computer Science")
    s2_pk = student_repo.create_student("CS002", "Daniel Radcliffe", "Computer Science")
    s3_pk = student_repo.create_student("IT001", "Rupert Grint", "Information Technology")

    yield service, student_repo, att_repo, (s1_pk, s2_pk, s3_pk)

    if test_db.exists():
        test_db.unlink()


def test_mark_face_attendance_success(attendance_setup):
    service, _, _, (s1, s2, s3) = attendance_setup
    res = service.mark_face_attendance(s1, "CS001", "Emma Watson")
    assert res["success"] is True
    assert res["status"] == "marked"
    assert "Attendance recorded" in res["message"]


def test_duplicate_attendance_prevented(attendance_setup):
    service, _, _, (s1, s2, s3) = attendance_setup
    # First mark
    res1 = service.mark_face_attendance(s1, "CS001", "Emma Watson")
    assert res1["success"] is True

    # Immediate second mark attempt on same day must be rejected
    res2 = service.mark_face_attendance(s1, "CS001", "Emma Watson")
    assert res2["success"] is False
    assert res2["status"] == "already_marked"


def test_database_unique_constraint_enforcement(attendance_setup):
    _, _, att_repo, (s1, s2, s3) = attendance_setup
    # Direct repository insert
    att_repo.record_attendance(s2, "2026-10-18", "09:00:00", "facial_recognition")

    # Second attempt with same date must raise DuplicateAttendanceError
    with pytest.raises(DuplicateAttendanceError):
        att_repo.record_attendance(s2, "2026-10-18", "09:05:00", "manual")


def test_attendance_percentage_calculation(attendance_setup):
    service, _, _, (s1, s2, s3) = attendance_setup
    # Total active students = 3
    # Mark 1 student present today
    service.mark_face_attendance(s1, "CS001", "Emma Watson")

    stats = service.get_dashboard_summary()
    assert stats["total_students"] == 3
    assert stats["marked_today"] == 1
    assert stats["unmarked_today"] == 2
    # 1/3 * 100 = 33.3%
    assert stats["attendance_percentage"] == 33.3

    # Mark second student
    service.mark_face_attendance(s2, "CS002", "Daniel Radcliffe")
    stats2 = service.get_dashboard_summary()
    assert stats2["marked_today"] == 2
    # 2/3 * 100 = 66.7%
    assert stats2["attendance_percentage"] == 66.7


def test_csv_export(attendance_setup):
    service, _, _, (s1, s2, s3) = attendance_setup
    service.mark_face_attendance(s1, "CS001", "Emma Watson")

    csv_text = service.export_csv()
    assert "Record ID,Student ID,Full Name,Department,Email,Date,Time,Source" in csv_text
    assert "CS001,Emma Watson,Computer Science" in csv_text
