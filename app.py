import logging
import os
import sys
from pathlib import Path
from flask import Flask, render_template

from config import Config
from services.auth_service import get_current_user

# Ensure base directory exists in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def configure_logging(app: Flask):
    """Set up structured logging to both file and console."""
    log_dir = Config.LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(str(Config.LOG_FILE), encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    app.logger.handlers = root_logger.handlers
    app.logger.setLevel(log_level)


def create_app(config_class=Config) -> Flask:
    """Application factory for Flask attendance system."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    configure_logging(app)
    app.logger.info(f"Initializing Facial Attendance Application [Mode: {app.config['APP_MODE']}]")

    # Ensure required runtime directories exist
    Config.DATASET_DIR.mkdir(parents=True, exist_ok=True)
    Config.ENCODINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

    from services.database_service import DatabaseService
    app._db_service = DatabaseService(config_class)

    # Register Blueprints
    from routes.auth_routes import auth_bp
    from routes.dashboard_routes import dashboard_bp
    from routes.student_routes import student_bp
    from routes.recognition_routes import recognition_bp
    from routes.attendance_routes import attendance_bp
    from routes.settings_routes import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(recognition_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(settings_bp)

    # Context processor to inject common user and status variables into all templates
    @app.context_processor
    def inject_global_template_context():
        user = get_current_user()
        return {
            "current_user": user,
            "app_mode": app.config.get("APP_MODE", "LOCAL"),
            "app_title": "Facial Attendance System"
        }

    # Custom Error Handlers
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template(
            "error.html",
            error_code=400,
            error_title="Bad Request",
            error_message="The request could not be processed due to invalid parameters or missing CSRF token."
        ), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template(
            "error.html",
            error_code=403,
            error_title="Access Forbidden",
            error_message="You do not have permission to view or execute this action."
        ), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template(
            "error.html",
            error_code=404,
            error_title="Page Not Found",
            error_message="The requested resource or page was not found on this server."
        ), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"Internal server error: {e}", exc_info=True)
        return render_template(
            "error.html",
            error_code=500,
            error_title="Internal Server Error",
            error_message="An unexpected server error occurred. Technical details have been safely logged."
        ), 500

    return app


if __name__ == "__main__":
    application = create_app()
    host = application.config.get("HOST", "127.0.0.1")
    port = application.config.get("PORT", 5000)
    application.logger.info(f"Starting server on http://{host}:{port}")
    application.run(host=host, port=port, debug=False)
