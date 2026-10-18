import logging
from typing import Any, Dict, Optional
from services.database_service import DatabaseService, get_db_service

logger = logging.getLogger("attendance.repositories.admin")


class AdminRepository:
    def __init__(self, db_service: Optional[DatabaseService] = None):
        self._db = db_service

    @property
    def db(self) -> DatabaseService:
        if self._db is not None:
            return self._db
        return get_db_service()

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT id, username, password_hash, role, is_active, created_at FROM admin_users WHERE username = %s"
        return self.db.fetch_one(sql, (username,))

    def get_by_id(self, admin_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT id, username, password_hash, role, is_active, created_at FROM admin_users WHERE id = %s"
        return self.db.fetch_one(sql, (admin_id,))

    def create_admin(self, username: str, password_hash: str, role: str = "admin", is_active: int = 1) -> int:
        sql = """
            INSERT INTO admin_users (username, password_hash, role, is_active)
            VALUES (%s, %s, %s, %s)
        """
        return self.db.execute_insert(sql, (username, password_hash, role, is_active))

    def count_admins(self) -> int:
        sql = "SELECT COUNT(*) as total FROM admin_users"
        row = self.db.fetch_one(sql)
        return row["total"] if row else 0

    def update_password(self, admin_id: int, new_password_hash: str) -> bool:
        sql = "UPDATE admin_users SET password_hash = %s WHERE id = %s"
        return self.db.execute_query(sql, (new_password_hash, admin_id)) > 0
