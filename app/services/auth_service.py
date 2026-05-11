import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_reset_token,
    create_verification_token,
    verify_token,
)


class AuthService:
    def __init__(self):
        self.db_path = Path(settings.USERS_DB)
        if not self.db_path.is_absolute():
            self.db_path = settings.BASE_DIR / self.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_user_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), check_same_thread=False)

    def _create_user_table(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                '''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    email TEXT UNIQUE,
                    hashed_password TEXT,
                    role TEXT,
                    department TEXT,
                    formulary TEXT,
                    alerts INTEGER,
                    is_active INTEGER,
                    is_verified INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    specialty TEXT,
                    search_count INTEGER DEFAULT 0
                )'''
            )
            # Migration: Add specialty column if it doesn't exist
            try:
                conn.execute('ALTER TABLE users ADD COLUMN specialty TEXT')
            except sqlite3.OperationalError:
                pass # Already exists
                
            # Migration: Add search_count column if it doesn't exist
            try:
                conn.execute('ALTER TABLE users ADD COLUMN search_count INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass # Already exists
                
            conn.commit()
        finally:
            conn.close()

    def _row_to_user(self, row: Any) -> Dict[str, Any]:
        # Handle both sqlite3.Row and tuple
        if isinstance(row, sqlite3.Row):
            d = dict(row)
        else:
            # Fallback for index-based access if Row factory isn't used
            # Based on the CREATE TABLE order
            cols = ['id', 'name', 'email', 'hashed_password', 'role', 'department', 'formulary', 
                    'alerts', 'is_active', 'is_verified', 'created_at', 'updated_at', 'specialty', 'search_count']
            d = {cols[i]: row[i] for i in range(min(len(row), len(cols)))}

        return {
            'id': d.get('id'),
            'name': d.get('name'),
            'email': d.get('email'),
            'role': d.get('role') or 'User',
            'department': d.get('department') or 'General',
            'formulary': d.get('formulary') or 'commercial',
            'alerts': bool(d.get('alerts')) if d.get('alerts') is not None else True,
            'is_active': bool(d.get('is_active')),
            'is_verified': bool(d.get('is_verified')),
            'created_at': d.get('created_at'),
            'specialty': d.get('specialty') or 'N/A',
            'search_count': d.get('search_count') or 0
        }

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM users WHERE email = ?', (email.lower().strip(),))
            row = cursor.fetchone()
            return self._row_to_user(row) if row else None
        finally:
            conn.close()

    def register_user(self, name: str, email: str, password: str, role: str = 'User') -> Dict[str, Any]:
        email = email.lower().strip()
        if self.get_user_by_email(email):
            raise ValueError('A user already exists with that email address.')

        hashed_password = get_password_hash(password)
        now = datetime.utcnow().isoformat()
        conn = self._connect()
        try:
            conn.execute(
                '''INSERT INTO users (name, email, hashed_password, role, department, formulary, alerts, is_active, is_verified, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, email, hashed_password, role, 'General', 'commercial', 1, 1, 0, now, now)
            )
            conn.commit()
        finally:
            conn.close()

        user = self.get_user_by_email(email)
        return user

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM users WHERE email = ?', (email.lower().strip(),))
            row = cursor.fetchone()
            if row and verify_password(password, row['hashed_password']):
                return self._row_to_user(row)
        finally:
            conn.close()
        return None

    def create_access_token_for_user(self, user: Dict[str, Any]) -> str:
        return create_access_token({'sub': user['email'], 'name': user.get('name'), 'role': user.get('role')})

    def request_password_reset(self, email: str) -> str:
        user = self.get_user_by_email(email)
        if not user:
            raise ValueError('Account not found for that email address.')
        return create_reset_token(user['email'])

    def reset_password(self, token: str, new_password: str) -> bool:
        user_email = verify_token(token, 'reset')
        if not user_email:
            return False

        conn = self._connect()
        try:
            hashed_password = get_password_hash(new_password)
            now = datetime.utcnow().isoformat()
            conn.execute(
                'UPDATE users SET hashed_password = ?, updated_at = ? WHERE email = ?',
                (hashed_password, now, user_email.lower().strip())
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def change_password(self, email: str, current_password: str, new_password: str) -> bool:
        user = self.authenticate_user(email, current_password)
        if not user:
            return False

        conn = self._connect()
        try:
            hashed_password = get_password_hash(new_password)
            now = datetime.utcnow().isoformat()
            conn.execute(
                'UPDATE users SET hashed_password = ?, updated_at = ? WHERE email = ?',
                (hashed_password, now, email.lower().strip())
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def verify_user(self, token: str) -> bool:
        user_email = verify_token(token, 'verify')
        if not user_email:
            return False

        conn = self._connect()
        try:
            conn.execute('UPDATE users SET is_verified = 1, updated_at = ? WHERE email = ?',
                         (datetime.utcnow().isoformat(), user_email.lower().strip()))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def get_or_create_user_from_oauth(self, name: str, email: str, provider: str) -> Dict[str, Any]:
        """Get an existing user by email or create a new one if they don't exist."""
        email = email.lower().strip()
        user = self.get_user_by_email(email)
        
        if user:
            # Update name if it's empty or placeholder
            if not user.get('name') or user.get('name') == 'User':
                conn = self._connect()
                try:
                    conn.execute('UPDATE users SET name = ?, updated_at = ? WHERE email = ?',
                                 (name, datetime.utcnow().isoformat(), email))
                    conn.commit()
                finally:
                    conn.close()
                user['name'] = name
            return user

        # Create new user
        now = datetime.utcnow().isoformat()
        conn = self._connect()
        try:
            # We don't have a password for OAuth users, so we leave it empty or set a random one
            # Using a placeholder since hashed_password cannot be NULL in some schemas
            hashed_placeholder = "OAUTH_USER_NO_PASSWORD" 
            conn.execute(
                '''INSERT INTO users (name, email, hashed_password, role, department, formulary, alerts, is_active, is_verified, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, email, hashed_placeholder, 'User', 'General', 'commercial', 1, 1, 1, now, now)
            )
            conn.commit()
        finally:
            conn.close()

        return self.get_user_by_email(email)
