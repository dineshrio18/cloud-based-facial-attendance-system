import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("attendance.database")

try:
    import mysql.connector
    from mysql.connector import errorcode, pooling
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger.warning("mysql-connector-python is not installed. Cloud MySQL/RDS mode will not be available.")


class DatabaseService:
    """Unified database service supporting SQLite for Local mode and AWS RDS MySQL for Cloud mode.
    
    Provides transparent parameter adaptation (%s to ? for SQLite), connection pooling,
    health checking, and robust transaction management.
    """

    _instance: Optional["DatabaseService"] = None
    _mysql_pool: Optional[Any] = None

    def __init__(self, config=None):
        if config is None:
            from config import Config
            self.config = Config
        else:
            self.config = config
        
        self.mode = self.config.APP_MODE.upper()
        self._init_pool()

    def _init_pool(self):
        """Initialize connection pool for MySQL if in CLOUD mode and configured."""
        if self.mode == "CLOUD":
            if not MYSQL_AVAILABLE:
                logger.error("Cloud mode configured but mysql.connector is unavailable.")
                return
            
            valid, missing = self.config.validate_rds_config()
            if not valid:
                logger.warning(f"RDS MySQL configuration incomplete. Missing variables: {', '.join(missing)}")
                return

            try:
                connect_args = {
                    "pool_name": "rds_facial_pool",
                    "pool_size": 5,
                    "pool_reset_session": True,
                    "host": self.config.DB_HOST,
                    "port": self.config.DB_PORT,
                    "database": self.config.DB_NAME,
                    "user": self.config.DB_USER,
                    "password": self.config.DB_PASSWORD,
                    "connection_timeout": self.config.DB_CONNECT_TIMEOUT,
                }
                if self.config.DB_SSL_CA:
                    connect_args["ssl_ca"] = self.config.DB_SSL_CA
                    connect_args["ssl_verify_cert"] = True

                self._mysql_pool = pooling.MySQLConnectionPool(**connect_args)
                logger.info(f"Initialized MySQL connection pool for RDS ({self.config.DB_HOST}:{self.config.DB_PORT})")
            except Exception as e:
                logger.error(f"Failed to initialize RDS MySQL connection pool: {e}")
                self._mysql_pool = None

    def get_connection(self):
        """Retrieve a raw database connection based on active APP_MODE."""
        if self.mode == "CLOUD":
            if not MYSQL_AVAILABLE:
                raise RuntimeError("mysql-connector-python is not installed. Cannot connect to RDS MySQL.")
            if self._mysql_pool:
                try:
                    return self._mysql_pool.get_connection()
                except Exception as e:
                    logger.warning(f"Failed to get connection from pool: {e}. Attempting direct connection.")
            
            # Direct connection attempt if pool is empty or failed
            connect_args = {
                "host": self.config.DB_HOST,
                "port": self.config.DB_PORT,
                "database": self.config.DB_NAME,
                "user": self.config.DB_USER,
                "password": self.config.DB_PASSWORD,
                "connection_timeout": self.config.DB_CONNECT_TIMEOUT,
            }
            if self.config.DB_SSL_CA:
                connect_args["ssl_ca"] = self.config.DB_SSL_CA
                connect_args["ssl_verify_cert"] = True
            return mysql.connector.connect(**connect_args)
        else:
            # SQLite for LOCAL mode
            db_path = self.config.LOCAL_DB_PATH
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn

    def adapt_query(self, sql: str) -> str:
        """Translate standard %s placeholder to ? placeholder when operating on SQLite."""
        if self.mode != "CLOUD":
            # For SQLite, convert %s to ?
            # Note: Do not convert if escaped or inside literal, but our queries use standard %s params
            return sql.replace("%s", "?")
        return sql

    def execute_query(self, sql: str, params: Optional[Tuple] = None) -> int:
        """Execute a write statement (INSERT, UPDATE, DELETE) and return affected row count."""
        adapted_sql = self.adapt_query(sql)
        params = params or ()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(adapted_sql, params)
            rowcount = cursor.rowcount
            conn.commit()
            cursor.close()
            return rowcount
        except Exception as e:
            conn.rollback()
            logger.error(f"Database execute error on query: {adapted_sql} - Error: {e}")
            raise
        finally:
            conn.close()

    def execute_insert(self, sql: str, params: Optional[Tuple] = None) -> int:
        """Execute an INSERT statement and return the inserted lastrowid."""
        adapted_sql = self.adapt_query(sql)
        params = params or ()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(adapted_sql, params)
            last_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return last_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Database insert error on query: {adapted_sql} - Error: {e}")
            raise
        finally:
            conn.close()

    def fetch_one(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Execute a SELECT statement and return a single row as a dictionary."""
        adapted_sql = self.adapt_query(sql)
        params = params or ()
        conn = self.get_connection()
        try:
            if self.mode == "CLOUD":
                cursor = conn.cursor(dictionary=True)
            else:
                cursor = conn.cursor()
            cursor.execute(adapted_sql, params)
            row = cursor.fetchone()
            cursor.close()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def fetch_all(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Execute a SELECT statement and return all rows as dictionaries."""
        adapted_sql = self.adapt_query(sql)
        params = params or ()
        conn = self.get_connection()
        try:
            if self.mode == "CLOUD":
                cursor = conn.cursor(dictionary=True)
            else:
                cursor = conn.cursor()
            cursor.execute(adapted_sql, params)
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def health_check(self) -> Dict[str, Any]:
        """Perform an active connectivity and latency health check on the configured database."""
        start_time = time.time()
        result = {
            "mode": self.mode,
            "connected": False,
            "target": str(self.config.DB_HOST) if self.mode == "CLOUD" else str(self.config.LOCAL_DB_PATH.name),
            "latency_ms": 0.0,
            "error": None
        }

        if self.mode == "CLOUD":
            valid, missing = self.config.validate_rds_config()
            if not valid:
                result["error"] = f"Incomplete RDS configuration: missing {', '.join(missing)}"
                return result

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            latency = (time.time() - start_time) * 1000.0
            result["connected"] = True
            result["latency_ms"] = round(latency, 2)
            return result
        except Exception as e:
            result["error"] = str(e)
            result["latency_ms"] = round((time.time() - start_time) * 1000.0, 2)
            return result


# Singleton accessor
_db_service: Optional[DatabaseService] = None

def get_db_service(config=None) -> DatabaseService:
    global _db_service

    # If inside an active Flask request context with an app-specific config
    try:
        from flask import current_app
        if current_app and hasattr(current_app, "_db_service"):
            return current_app._db_service
    except (ImportError, RuntimeError):
        pass

    if config is not None:
        _db_service = DatabaseService(config)
        return _db_service

    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
