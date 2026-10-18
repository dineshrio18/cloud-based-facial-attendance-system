import functools
import logging
import secrets
from typing import Any, Dict, Optional
from flask import flash, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from repositories.admin_repository import AdminRepository

logger = logging.getLogger("attendance.auth")


class AuthService:
    def __init__(self, admin_repo: Optional[AdminRepository] = None):
        self.admin_repo = admin_repo or AdminRepository()

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify username and password against stored hashes."""
        if not username or not password:
            return None

        user = self.admin_repo.get_by_username(username.strip())
        if not user:
            logger.warning(f"Failed login attempt for nonexistent user: {username}")
            return None

        if not user.get("is_active"):
            logger.warning(f"Failed login attempt for inactive user: {username}")
            return None

        if check_password_hash(user["password_hash"], password):
            logger.info(f"Successful authentication for user: {username}")
            return user
        else:
            logger.warning(f"Failed password verification for user: {username}")
            return None

    def change_password(self, admin_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
        """Change administrator password after verifying the old password."""
        user = self.admin_repo.get_by_id(admin_id)
        if not user:
            return False, "User not found."

        if not check_password_hash(user["password_hash"], old_password):
            return False, "Current password is incorrect."

        if len(new_password) < 8:
            return False, "New password must be at least 8 characters long."

        new_hash = generate_password_hash(new_password)
        self.admin_repo.update_password(admin_id, new_hash)
        logger.info(f"Password updated successfully for admin_id={admin_id}")
        return True, "Password updated successfully."


# Session helper functions
def login_user(user: Dict[str, Any]) -> None:
    """Store authenticated user details in Flask session."""
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user.get("role", "admin")
    session["_csrf_token"] = secrets.token_hex(32)


def logout_user() -> None:
    """Clear Flask session upon logout."""
    session.clear()


def get_current_user() -> Optional[Dict[str, Any]]:
    """Retrieve logged-in user summary from session."""
    if "user_id" in session:
        return {
            "id": session["user_id"],
            "username": session["username"],
            "role": session.get("role", "admin"),
        }
    return None


def is_authenticated() -> bool:
    """Check if current request has a valid logged-in session."""
    return "user_id" in session


def generate_csrf_token() -> str:
    """Generate or retrieve a CSRF token for the current session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf_token(token: Optional[str]) -> bool:
    """Verify submitted CSRF token against session token."""
    session_token = session.get("_csrf_token")
    if not session_token or not token:
        return False
    return secrets.compare_digest(session_token, token)


def login_required(f):
    """Decorator to protect Flask view routes from unauthenticated access."""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            if request.is_json:
                return {"error": "Authentication required"}, 401
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function
