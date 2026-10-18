import pytest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app
from config import TestingConfig
from services.auth_service import AuthService, generate_csrf_token, validate_csrf_token
from repositories.admin_repository import AdminRepository
from services.database_service import DatabaseService
from database.init_db import init_sqlite_database, seed_admin_user


@pytest.fixture(scope="module")
def app_instance():
    # Setup test database
    test_db = TestingConfig.LOCAL_DB_PATH
    if test_db.exists():
        test_db.unlink()
    init_sqlite_database(test_db)

    db_service = DatabaseService(TestingConfig)
    admin_repo = AdminRepository(db_service)
    seed_admin_user(admin_repo, "testadmin", "TestPass@123")

    app = create_app(TestingConfig)
    yield app

    if test_db.exists():
        test_db.unlink()


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def test_password_verification(app_instance):
    db_service = DatabaseService(TestingConfig)
    admin_repo = AdminRepository(db_service)
    auth = AuthService(admin_repo)

    # Valid credentials
    user = auth.authenticate("testadmin", "TestPass@123")
    assert user is not None
    assert user["username"] == "testadmin"

    # Invalid password
    user_bad_pw = auth.authenticate("testadmin", "WrongPassword")
    assert user_bad_pw is None

    # Nonexistent user
    user_none = auth.authenticate("nonexistent", "SomePass")
    assert user_none is None


def test_csrf_token_validation(app_instance):
    with app_instance.test_request_context():
        token = generate_csrf_token()
        assert token is not None
        assert len(token) == 64
        # Validate correct token
        assert validate_csrf_token(token) is True
        # Reject bad token
        assert validate_csrf_token("invalid_token_here") is False
        assert validate_csrf_token(None) is False


def test_protected_route_requires_login(client):
    # Attempting to access dashboard without signing in
    res = client.get("/dashboard", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_successful_admin_login(client):
    # Fetch login page to retrieve CSRF token
    get_res = client.get("/login")
    assert get_res.status_code == 200

    with client.session_transaction() as sess:
        csrf = sess.get("_csrf_token")

    # Post login with correct credentials
    post_res = client.post("/login", data={
        "csrf_token": csrf,
        "username": "testadmin",
        "password": "TestPass@123"
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b"Overview" in post_res.data
    assert b"testadmin" in post_res.data
