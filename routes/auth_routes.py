import logging
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from services.auth_service import AuthService, generate_csrf_token, login_user, logout_user, validate_csrf_token

logger = logging.getLogger("attendance.routes.auth")
auth_bp = Blueprint("auth", __name__)
auth_service = AuthService()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    error_message = None

    if request.method == "POST":
        csrf_token = request.form.get("csrf_token")
        if not validate_csrf_token(csrf_token):
            error_message = "Invalid security token. Please refresh the page and try again."
            return render_template("login.html", error=error_message, csrf_token=generate_csrf_token()), 400

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            error_message = "Please enter both username and password."
        else:
            user = auth_service.authenticate(username, password)
            if user:
                login_user(user)
                flash(f"Welcome back, {user['username']}!", "success")
                next_url = request.args.get("next")
                if next_url and next_url.startswith("/"):
                    return redirect(next_url)
                return redirect(url_for("dashboard.index"))
            else:
                error_message = "Invalid username or password. Please try again."

    return render_template("login.html", error=error_message, csrf_token=generate_csrf_token())


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("auth.login"))
