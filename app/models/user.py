from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = Field(default="User")
    email: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = Field(default="User")
    department: str = Field(default="General")
    formulary: str = Field(default="commercial")
    alerts: bool = Field(default=True)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    specialty: str = Field(default="N/A")
    search_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(SQLModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "User"

class UserLogin(SQLModel):
    email: str
    password: str
