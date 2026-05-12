from typing import Optional
from sqlmodel import SQLModel, Field

class SearchCache(SQLModel, table=True):
    __tablename__ = "search_cache"
    
    key: str = Field(primary_key=True)
    value: str
    expires_at: float
