from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class ProcessedDrug(SQLModel, table=True):
    __tablename__ = "processed_drugs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    drug_name: str = Field(index=True)
    generic_name: Optional[str] = Field(default=None, index=True)
    therapeutic_class: Optional[str] = Field(default=None, index=True)
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    indication: Optional[str] = None
    plan_id: Optional[str] = Field(default=None, index=True)
    source_pdf: Optional[str] = None
    page_number: Optional[int] = None
    is_insured: bool = False
    safety_score: int = 100
    created_at: datetime = Field(default_factory=datetime.utcnow)
