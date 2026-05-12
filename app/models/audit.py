from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user: str
    action: str
    target: str
    type: str
    status: str = "Success"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
