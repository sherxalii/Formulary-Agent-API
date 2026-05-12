from sqlmodel import create_engine, SQLModel, Session
from app.core.config import settings
from typing import Generator
import app.models # Register all models for create_all()

# Create engine
# check_same_thread=False is needed only for SQLite
connect_args = {"check_same_thread": False} if "sqlite" in settings.SQLALCHEMY_DATABASE_URL else {}

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL, 
    echo=settings.DEBUG, 
    connect_args=connect_args
)

def init_db():
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    with Session(engine) as session:
        yield session
