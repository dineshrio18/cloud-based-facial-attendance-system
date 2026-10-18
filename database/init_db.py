import argparse
import logging
import os
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import Config
from services.database_service import get_db_service
from repositories.admin_repository import AdminRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_db")


def init_sqlite_database(db_path: Path):
    """Initialize local SQLite database schema."""
    logger.info(f"Initializing SQLite database at: {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema_file = BASE_DIR / "database" / "schema_sqlite.sql"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_file}")

    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
        logger.info("SQLite schema applied successfully.")
    finally:
        conn.close()


def init_mysql_database(config):
    """Initialize AWS RDS MySQL database schema."""
    logger.info(f"Initializing AWS RDS MySQL database at {config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}")
    valid, missing = config.validate_rds_config()
    if not valid:
        logger.error(f"Cannot initialize MySQL. Missing configuration: {', '.join(missing)}")
        return False

    import mysql.connector

    schema_file = BASE_DIR / "database" / "schema.sql"
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Split commands by semicolon while ignoring comments
    statements = []
    current_stmt = []
    for line in schema_sql.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("--"):
            continue
        current_stmt.append(line)
        if line_clean.endswith(";"):
            statements.append("\n".join(current_stmt))
            current_stmt = []

    connect_args = {
        "host": config.DB_HOST,
        "port": config.DB_PORT,
        "user": config.DB_USER,
        "password": config.DB_PASSWORD,
        "connection_timeout": config.DB_CONNECT_TIMEOUT,
    }
    if config.DB_SSL_CA:
        connect_args["ssl_ca"] = config.DB_SSL_CA
        connect_args["ssl_verify_cert"] = True

    try:
        conn = mysql.connector.connect(**connect_args)
        cursor = conn.cursor()
        for stmt in statements:
            if stmt.strip():
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    logger.warning(f"Notice on statement: {e}")
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("MySQL/RDS schema applied successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize RDS MySQL database: {e}")
        return False


def seed_admin_user(admin_repo: AdminRepository, username: str, password: str) -> bool:
    """Create default initial administrator if no admin users currently exist."""
    existing = admin_repo.count_admins()
    if existing > 0:
        logger.info(f"Admin users already exist ({existing} found). Skipping default admin creation.")
        return True

    logger.info(f"Creating initial administrator account: {username}")
    pw_hash = generate_password_hash(password)
    admin_repo.create_admin(username=username, password_hash=pw_hash, role="admin", is_active=1)
    logger.info(f"Administrator '{username}' created successfully.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Initialize database schema and administrator user.")
    parser.add_argument("--mode", choices=["LOCAL", "CLOUD"], default=None, help="Database target mode")
    parser.add_argument("--admin-username", default="admin", help="Initial admin username (default: admin)")
    parser.add_argument("--admin-password", default="Admin@123", help="Initial admin password (default: Admin@123)")
    args = parser.parse_args()

    mode = args.mode or Config.APP_MODE
    logger.info(f"Running database initialization for mode: {mode}")

    if mode == "CLOUD":
        success = init_mysql_database(Config)
        if not success:
            logger.error("Could not complete RDS MySQL initialization.")
            sys.exit(1)
    else:
        init_sqlite_database(Config.LOCAL_DB_PATH)

    # Seed admin user
    db = get_db_service()
    admin_repo = AdminRepository(db)
    seed_admin_user(admin_repo, args.admin_username, args.admin_password)

    logger.info("Database initialization completed successfully.")


if __name__ == "__main__":
    main()
