import os
import json
import traceback
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pymysql
from contextlib import contextmanager

# Toggle verbose debug logs with env
DEBUG_DB = os.environ.get("YEARPLAN_DEBUG_DB", "0") in {"1", "true", "True", "yes"}

class MySQLStorage:
    def __init__(self, connection_config: Dict[str, str] = None):
        """Initialize MySQL storage with connection configuration"""
        if connection_config is None:
            # Default configuration from environment variables
            self.config = {
                'host': os.environ.get('MYSQL_HOST', 'localhost'),
                'user': os.environ.get('MYSQL_USER', 'yearplan_user'),
                'password': os.environ.get('MYSQL_PASSWORD', 'secure_password_here'),
                'database': os.environ.get('MYSQL_DATABASE', 'yearplan_db'),
                'charset': 'utf8mb4',
                'autocommit': True
            }
        else:
            self.config = connection_config
        
        # Initialize database tables
        self._create_tables()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        connection = None
        try:
            if DEBUG_DB:
                print(f"[DB] Connecting with config: {{'host': '{self.config.get('host')}', 'user': '{self.config.get('user')}', 'database': '{self.config.get('database')}', 'charset': '{self.config.get('charset')}', 'autocommit': {self.config.get('autocommit')}}}")
            connection = pymysql.connect(**self.config)
            yield connection
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[DB] Connection error: {e}\n{tb}")
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            # Do not swallow; propagate to caller so app can return 500 with details
            raise
        finally:
            if connection:
                try:
                    connection.close()
                except Exception:
                    pass

    def _create_tables(self):
        """Create database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    verification_token VARCHAR(255) UNIQUE,
                    token_expires DATETIME,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_email (email),
                    INDEX idx_verification_token (verification_token)
                )
            """)
            
            # Goals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_email VARCHAR(255) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    target_date DATE,
                    status ENUM('active', 'completed', 'paused', 'cancelled') DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_email) REFERENCES users(email) ON DELETE CASCADE,
                    INDEX idx_user_email (user_email),
                    INDEX idx_status (status),
                    INDEX idx_target_date (target_date)
                )
            """)
            
            # Milestones table (for future use)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS milestones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    goal_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    target_date DATE,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_at DATETIME NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,
                    INDEX idx_goal_id (goal_id),
                    INDEX idx_target_date (target_date)
                )
            """)

            # Goal logs table to track progress
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS goal_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    goal_id INT NOT NULL,
                    user_email VARCHAR(255) NOT NULL,
                    action ENUM('increment','decrement','update') NOT NULL,
                    value DOUBLE NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE,
                    INDEX idx_goal_id (goal_id),
                    INDEX idx_user_email (user_email),
                    INDEX idx_created_at (created_at)
                )
                """
            )
            
            conn.commit()

    def add_user(self, email: str, password: str, verification_token: str, token_expires: str) -> bool:
        """Add a new user to the database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] add_user email={email}")
            # Check if user already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                if DEBUG_DB:
                    print("[DB] add_user: user exists")
                return False

            # Convert token_expires string to datetime
            expires_dt = datetime.strptime(token_expires, '%Y-%m-%d %H:%M:%S')

            # Insert new user
            cursor.execute(
                """
                INSERT INTO users (email, password, verification_token, token_expires, is_verified)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (email, password, verification_token, expires_dt, False),
            )

            conn.commit()
            return True

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user login"""
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] authenticate_user email={email}")

            cursor.execute(
                """
                SELECT id, email, password, is_verified, created_at
                FROM users WHERE email = %s
                """,
                (email,),
            )

            user = cursor.fetchone()
            if user and user['password'] == password:  # TODO: hash in production
                return user
            return None

    def verify_user_email(self, token: str) -> bool:
        """Verify user email with token"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] verify_user_email token={token}")

            # Find user with matching token
            cursor.execute(
                """
                SELECT id, email, token_expires, is_verified 
                FROM users WHERE verification_token = %s
                """,
                (token,),
            )

            user = cursor.fetchone()
            if not user:
                return False

            user_id, email, token_expires, is_verified = user

            # Check if already verified
            if is_verified:
                return False

            # Check if token expired
            if datetime.utcnow() > token_expires:
                return False

            # Mark as verified
            cursor.execute(
                """
                UPDATE users SET is_verified = TRUE, verification_token = NULL
                WHERE id = %s
                """,
                (user_id,),
            )

            conn.commit()
            return True

    def add_goal(self, user_email: str, title: str, description: str, target_date: str) -> Optional[Dict[str, Any]]:
        """Add a new goal for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] add_goal user_email={user_email} title={title}")

            # Verify user exists and is verified
            cursor.execute(
                """
                SELECT id FROM users WHERE email = %s AND is_verified = TRUE
                """,
                (user_email,),
            )

            if not cursor.fetchone():
                return None

            # Insert goal
            cursor.execute(
                """
                INSERT INTO goals (user_email, title, description, target_date, status)
                VALUES (%s, %s, %s, %s, 'active')
                """,
                (user_email, title, description, target_date),
            )

            goal_id = cursor.lastrowid

            # Fetch the created goal
            cursor.execute(
                """
                SELECT id, user_email, title, description, target_date, status, created_at
                FROM goals WHERE id = %s
                """,
                (goal_id,),
            )

            goal = cursor.fetchone()
            conn.commit()
            return goal

    def get_user_goals(self, user_email: str) -> List[Dict[str, Any]]:
        """Get all goals for a specific user"""
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] get_user_goals user_email={user_email}")

            cursor.execute(
                """
                SELECT id, user_email, title, description, target_date, status, created_at, updated_at
                FROM goals WHERE user_email = %s ORDER BY created_at DESC
                """,
                (user_email,),
            )

            return cursor.fetchall()

    def update_goal_status(self, goal_id: int, status: str, user_email: str) -> bool:
        """Update goal status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] update_goal_status id={goal_id} status={status} user={user_email}")

            cursor.execute(
                """
                UPDATE goals SET status = %s 
                WHERE id = %s AND user_email = %s
                """,
                (status, goal_id, user_email),
            )

            conn.commit()
            return cursor.rowcount > 0

    def get_goal_for_user(self, goal_id: int, user_email: str) -> Optional[Dict[str, Any]]:
        """Fetch a single goal by id for a given user."""
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] get_goal_for_user id={goal_id} user={user_email}")
            cursor.execute(
                """
                SELECT id, user_email, title, description, target_date, status, created_at, updated_at
                FROM goals WHERE id = %s AND user_email = %s
                """,
                (goal_id, user_email),
            )
            return cursor.fetchone()

    def update_goal_title(self, goal_id: int, user_email: str, title: str) -> bool:
        """Update the title of a goal, ensuring it belongs to the user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] update_goal_title id={goal_id} title={title} user={user_email}")
            cursor.execute(
                """
                UPDATE goals SET title = %s WHERE id = %s AND user_email = %s
                """,
                (title, goal_id, user_email),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_goal_description(self, goal_id: int, user_email: str, description: str) -> bool:
        """Update the description JSON for a goal, ensuring it belongs to the user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] update_goal_description id={goal_id} user={user_email}")
            cursor.execute(
                """
                UPDATE goals SET description = %s WHERE id = %s AND user_email = %s
                """,
                (description, goal_id, user_email),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_goal(self, goal_id: int, user_email: str) -> bool:
        """Delete a goal if it belongs to the user. goal_logs will cascade delete."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] delete_goal id={goal_id} user={user_email}")
            cursor.execute(
                """
                DELETE FROM goals WHERE id = %s AND user_email = %s
                """,
                (goal_id, user_email),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] get_user_by_email email={email}")

            cursor.execute(
                """
                SELECT id, email, is_verified, created_at
                FROM users WHERE email = %s
                """,
                (email,),
            )

            return cursor.fetchone()

    # --------------------
    # Logs operations
    # --------------------
    def add_goal_log(self, goal_id: int, user_email: str, action: str, value: float) -> Optional[Dict[str, Any]]:
        """Insert a log row and return the created log."""
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] add_goal_log goal_id={goal_id} user={user_email} action={action} value={value}")
            cursor.execute(
                """
                INSERT INTO goal_logs (goal_id, user_email, action, value)
                VALUES (%s, %s, %s, %s)
                """,
                (goal_id, user_email, action, float(value)),
            )
            log_id = cursor.lastrowid
            cursor.execute(
                """
                SELECT id, goal_id, user_email, action, value, created_at
                FROM goal_logs WHERE id = %s
                """,
                (log_id,),
            )
            row = cursor.fetchone()
            conn.commit()
            return row

    def get_goal_logs(self, goal_id: int, user_email: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] get_goal_logs goal_id={goal_id} user={user_email}")
            cursor.execute(
                """
                SELECT id, goal_id, user_email, action, value, created_at
                FROM goal_logs WHERE goal_id = %s AND user_email = %s
                ORDER BY created_at DESC, id DESC
                """,
                (goal_id, user_email),
            )
            return cursor.fetchall()

    def get_all_logs_for_user(self, user_email: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            if DEBUG_DB:
                print(f"[DB] get_all_logs_for_user user={user_email}")
            cursor.execute(
                """
                SELECT id, goal_id, user_email, action, value, created_at
                FROM goal_logs WHERE user_email = %s
                ORDER BY created_at DESC, id DESC
                """,
                (user_email,),
            )
            return cursor.fetchall()

    def delete_log(self, log_id: int, user_email: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] delete_log id={log_id} user={user_email}")
            cursor.execute(
                """
                DELETE FROM goal_logs WHERE id = %s AND user_email = %s
                """,
                (log_id, user_email),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_verification_token(self, email: str, token: str, token_expires: str) -> bool:
        """Set/refresh the user's verification token and expiry, and mark as unverified."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print(f"[DB] update_verification_token email={email}")

            # Convert token_expires string to datetime if needed
            if isinstance(token_expires, str):
                expires_dt = datetime.strptime(token_expires, '%Y-%m-%d %H:%M:%S')
            else:
                expires_dt = token_expires

            cursor.execute(
                """
                UPDATE users
                SET verification_token = %s, token_expires = %s, is_verified = FALSE
                WHERE email = %s
                """,
                (token, expires_dt, email),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, int]:
        """Get basic statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if DEBUG_DB:
                print("[DB] get_stats")

            # Count users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]

            # Count verified users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_verified = TRUE")
            verified_users = cursor.fetchone()[0]

            # Count goals
            cursor.execute("SELECT COUNT(*) FROM goals")
            goal_count = cursor.fetchone()[0]

            # Count completed goals
            cursor.execute("SELECT COUNT(*) FROM goals WHERE status = 'completed'")
            completed_goals = cursor.fetchone()[0]

            return {
                'total_users': user_count,
                'verified_users': verified_users,
                'total_goals': goal_count,
                'completed_goals': completed_goals,
            }

# Compatibility alias for existing code
YearPlanStorage = MySQLStorage