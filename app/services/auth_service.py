from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User
from app.core.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_reset_token,
    verify_token,
)

class AuthService:
    def __init__(self):
        # We don't need to manually create tables here anymore, 
        # as it will be handled in app/main.py init_db()
        pass

    def _user_to_dict(self, user: User) -> Dict[str, Any]:
        """Convert User model to dictionary for backward compatibility."""
        if not user:
            return None
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role,
            'department': user.department,
            'formulary': user.formulary,
            'alerts': user.alerts,
            'is_active': user.is_active,
            'is_verified': user.is_verified,
            'created_at': user.created_at.isoformat() if isinstance(user.created_at, datetime) else user.created_at,
            'specialty': user.specialty,
            'search_count': user.search_count
        }

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with Session(engine) as session:
            statement = select(User).where(User.email == email.lower().strip())
            user = session.exec(statement).first()
            return self._user_to_dict(user) if user else None

    def register_user(self, name: str, email: str, password: str, role: str = 'User') -> Dict[str, Any]:
        email = email.lower().strip()
        if self.get_user_by_email(email):
            raise ValueError('A user already exists with that email address.')

        hashed_password = get_password_hash(password)
        user = User(
            name=name,
            email=email,
            hashed_password=hashed_password,
            role=role,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        with Session(engine) as session:
            session.add(user)
            session.commit()
            session.refresh(user)
            return self._user_to_dict(user)

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        with Session(engine) as session:
            statement = select(User).where(User.email == email.lower().strip())
            user = session.exec(statement).first()
            if user and verify_password(password, user.hashed_password):
                return self._user_to_dict(user)
        return None

    def create_access_token_for_user(self, user: Dict[str, Any]) -> str:
        return create_access_token({'sub': user['email'], 'name': user.get('name'), 'role': user.get('role')})

    def request_password_reset(self, email: str) -> str:
        user_dict = self.get_user_by_email(email)
        if not user_dict:
            raise ValueError('Account not found for that email address.')
        return create_reset_token(user_dict['email'])

    def reset_password(self, token: str, new_password: str) -> bool:
        user_email = verify_token(token, 'reset')
        if not user_email:
            return False

        with Session(engine) as session:
            statement = select(User).where(User.email == user_email.lower().strip())
            user = session.exec(statement).first()
            if user:
                user.hashed_password = get_password_hash(new_password)
                user.updated_at = datetime.utcnow()
                session.add(user)
                session.commit()
                return True
        return False

    def change_password(self, email: str, current_password: str, new_password: str) -> bool:
        user_dict = self.authenticate_user(email, current_password)
        if not user_dict:
            return False

        with Session(engine) as session:
            statement = select(User).where(User.email == email.lower().strip())
            user = session.exec(statement).first()
            if user:
                user.hashed_password = get_password_hash(new_password)
                user.updated_at = datetime.utcnow()
                session.add(user)
                session.commit()
                return True
        return False

    def verify_user(self, token: str) -> bool:
        user_email = verify_token(token, 'verify')
        if not user_email:
            return False

        with Session(engine) as session:
            statement = select(User).where(User.email == user_email.lower().strip())
            user = session.exec(statement).first()
            if user:
                user.is_verified = True
                user.updated_at = datetime.utcnow()
                session.add(user)
                session.commit()
                return True
        return False

    def get_or_create_user_from_oauth(self, name: str, email: str, provider: str) -> Dict[str, Any]:
        email = email.lower().strip()
        user_dict = self.get_user_by_email(email)
        
        if user_dict:
            # Update name if it's empty or placeholder
            if not user_dict.get('name') or user_dict.get('name') == 'User':
                with Session(engine) as session:
                    statement = select(User).where(User.email == email)
                    user = session.exec(statement).first()
                    if user:
                        user.name = name
                        user.updated_at = datetime.utcnow()
                        session.add(user)
                        session.commit()
                        session.refresh(user)
                        return self._user_to_dict(user)
            return user_dict

        # Create new user
        hashed_placeholder = "OAUTH_USER_NO_PASSWORD" 
        user = User(
            name=name,
            email=email,
            hashed_password=hashed_placeholder,
            role='User',
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        with Session(engine) as session:
            session.add(user)
            session.commit()
            session.refresh(user)
            return self._user_to_dict(user)
