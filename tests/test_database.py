import pytest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import TestingConfig
from services.database_service import DatabaseService
from repositories.student_repository import StudentRepository
from database.init_db import init_sqlite_database


@pytest.fixture
def db_service():
    test_db = TestingConfig.LOCAL_DB_PATH
    if test_db.exists():
        test_db.unlink()
    init_sqlite_database(test_db)
    service = DatabaseService(TestingConfig)
    yield service
    if test_db.exists():
        test_db.unlink()


def test_database_health_check(db_service):
    health = db_service.health_check()
    assert health["connected"] is True
    assert health["mode"] == "LOCAL"
    assert health["latency_ms"] >= 0.0
    assert health["error"] is None


def test_parameterized_queries_prevent_injection(db_service):
    repo = StudentRepository(db_service)
    # Attempt SQL injection string as student ID
    injection_id = "CS001'; DROP TABLE students; --"
    pk = repo.create_student(
        student_id=injection_id,
        full_name="Injection Test Subject",
        department="Security",
        email="test@sec.org"
    )
    assert pk > 0

    # Ensure table was not dropped and record exists safely
    student = repo.get_by_id(pk)
    assert student is not None
    assert student["student_id"] == injection_id


def test_duplicate_student_id_rejection(db_service):
    repo = StudentRepository(db_service)
    repo.create_student("STU-1001", "Alice Smith", "Computer Science")

    # Attempting to insert duplicate student_id must raise an exception
    with pytest.raises(Exception):
        repo.create_student("STU-1001", "Alice Duplicate", "Information Technology")


def test_student_crud_lifecycle(db_service):
    repo = StudentRepository(db_service)
    # Create
    pk = repo.create_student("STU-2001", "Bob Johnson", "Electronics", "bob@example.com")
    assert pk > 0

    # Read
    s = repo.get_by_id(pk)
    assert s["full_name"] == "Bob Johnson"
    assert s["status"] == "active"

    # Update
    updated = repo.update_student(pk, full_name="Robert Johnson", department="Robotics", email="rob@example.com", status="active")
    assert updated is True

    s_updated = repo.get_by_id(pk)
    assert s_updated["full_name"] == "Robert Johnson"
    assert s_updated["department"] == "Robotics"

    # Delete
    deleted = repo.delete_student(pk)
    assert deleted is True
    assert repo.get_by_id(pk) is None


def test_database_connection_failure_handling():
    class BadConfig(TestingConfig):
        LOCAL_DB_PATH = Path("Z:/non_existent_drive/invalid_path/test.db")

    bad_db = DatabaseService(BadConfig)
    health = bad_db.health_check()
    assert health["connected"] is False
    assert health["error"] is not None
