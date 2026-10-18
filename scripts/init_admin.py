import argparse
import logging
import sys
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from repositories.admin_repository import AdminRepository
from services.database_service import get_db_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_admin")


def create_or_update_admin(username: str, password: str, role: str = "admin"):
    db = get_db_service()
    admin_repo = AdminRepository(db)

    existing = admin_repo.get_by_username(username)
    pw_hash = generate_password_hash(password)

    if existing:
        admin_repo.update_password(existing["id"], pw_hash)
        logger.info(f"Updated password for existing administrator '{username}'.")
    else:
        admin_repo.create_admin(username=username, password_hash=pw_hash, role=role)
        logger.info(f"Created new administrator account '{username}'.")


def main():
    parser = argparse.ArgumentParser(description="Create or update an administrator account.")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--role", default="admin", help="Admin role (default: admin)")
    args = parser.parse_args()

    create_or_update_admin(args.username, args.password, args.role)


if __name__ == "__main__":
    main()
