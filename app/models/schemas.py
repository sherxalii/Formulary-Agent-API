import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# --- Base Models ---
class BaseResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

# --- Core Models ---

class PatientContext(BaseModel):
    id: Optional[str] = None
    age: Optional[int] = 0
    gender: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    pregnancy_status: Optional[str] = "not_pregnant"
    alcohol_use: Optional[str] = "no"
    age_group: Optional[str] = "adult"

class SafetyAlert(BaseModel):
    type: str # 'allergy', 'condition', 'age', 'ddi', 'coverage'
    severity: str # 'high', 'medium', 'low'
    message: str
    drugs: Optional[List[str]] = None # Particularly for DDI

class DrugAlternative(BaseModel):
    drug_name: str
    generic_name: Optional[str] = ""
    medicine_form: Optional[str] = ""
    dosage_form: Optional[str] = ""
    therapeutic_class: Optional[str] = ""
    safety_alerts: List[SafetyAlert] = Field(default_factory=list)
    risk_score: int = 0
    safety_score: int = 100
    rating: float = 0.0
    pregnancy_safe: bool = True
    safe: bool = True
    recommendation: Optional[str] = None

# --- Search Models ---

class SearchRequest(BaseModel):
    drug_name: str
    insurance_name: str
    patient_id: Optional[str] = ""
    patient_context: Optional[PatientContext] = None

class SearchResponse(BaseModel):
    success: bool
    primary_indication: Optional[str] = "NOT INSURED" # 'INSURED' or 'NOT INSURED'
    alternatives: List[DrugAlternative] = Field(default_factory=list)
    response_time_ms: float
    rxnorm_validation: bool = False
    rxnorm_validation_message: Optional[str] = None
    name_corrected: bool = False
    corrected_drug_name: Optional[str] = None
    patient_safety_summary: Optional[str] = None
    error: Optional[str] = None

# --- AI Models ---

class AIChatRequest(BaseModel):
    query: str
    intent: Optional[str] = "general"
    drugData: Optional[Dict[str, Any]] = None
    coverageData: Optional[Dict[str, Any]] = None
    patient_context: Optional[PatientContext] = None

class AIChatResponse(BaseResponse):
    response: Optional[str] = None
    intent: Optional[str] = None
    tokens_used: Optional[int] = None

class ChatResponse(BaseModel):
    success: bool
    response: str
    intent: Optional[str] = "general"
    sources: List[str] = Field(default_factory=list)
    drug_info: Optional[List[Dict[str, Any]]] = None
    formulary_info: Optional[List[Dict[str, Any]]] = None
    tokens_used: Optional[int] = None

# --- Database & System Models ---

class DatabaseInfo(BaseModel):
    id: str
    name: str
    filename: str
    status: str
    size: str
    uploadedAt: Optional[str] = None
    processed: bool
    drugCount: int
    genericPercent: float = 0.0
    tierCount: int = 4
    summary_text: Optional[str] = None

class DatabaseListResponse(BaseResponse):
    databases: List[DatabaseInfo]

class EmbeddingStatusResponse(BaseModel):
    status: str

class SystemInfo(BaseModel):
    service: str = "Clinical Agent RAG API"
    version: str = "1.0.0"
    status: str = "healthy"
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

class CacheStatus(BaseModel):
    cache_strategy: str
    total_cached_databases: int
    cached_databases: List[Dict[str, Any]]
    preloaded: bool
    pdf_cache_cleared: Optional[bool] = None

# --- Personalized Check Models ---

class PersonalizedCheckRequest(BaseModel):
    drugs: List[Union[str, Dict[str, Any]]]
    patient_id: Optional[str] = None
    patient_context: Optional[PatientContext] = None
    insurance_plan: Optional[str] = None

class PersonalizedCheckResponse(BaseResponse):
    results: List[Dict[str, Any]] = []

# --- Drug Info Models ---

class DrugInfoResponse(BaseResponse):
    drugName: Optional[str] = None
    rxNormId: Optional[str] = None
    atcCode: Optional[str] = None
    indication: Optional[str] = None
    dosage: List[str] = []
    sideEffects: List[str] = []
    contraindications: List[str] = []
    interactions: List[str] = []
    manufacturer: Optional[str] = None
    advancedInfo: Optional[Dict[str, Any]] = None

# ============================================================================
# Unified Drug System Schemas
# ============================================================================

class DDIWarningSchema(BaseModel):
    """Drug-Drug Interaction warning from UnifiedDrugSystem."""
    drug1: str
    drug2: str
    risk_level: str  # low | moderate | high | critical
    confidence: float
    shared_reactions: List[str] = []
    recommendation: str

class DDICheckRequest(BaseModel):
    """Two-drug DDI check request."""
    drug1: str
    drug2: str

class DDIBatchRequest(BaseModel):
    """Batch DDI check: one drug vs many."""
    primary_drug: str
    other_drugs: List[str]

class UnifiedPatientContext(BaseModel):
    """Patient context for recommendation engine."""
    age: Optional[int] = None
    pregnancy_status: Optional[str] = "not_pregnant"
    allergies: Optional[List[str]] = []
    kidney_disease: Optional[bool] = False
    liver_disease: Optional[bool] = False
    diabetes: Optional[bool] = False
    hypertension: Optional[bool] = False

class RecommendationRequest(BaseModel):
    """Drug recommendation request."""
    medical_condition: str
    patient_context: Optional[UnifiedPatientContext] = None
    current_medications: Optional[List[str]] = []
    num_recommendations: Optional[int] = 5

class DrugRecommendationSchema(BaseModel):
    """Single drug recommendation response."""
    drug_name: str
    confidence: float
    reasoning: List[str]
    side_effects: List[str]
    rating: float
    reviews: int
    ddi_warnings: List[DDIWarningSchema] = []

class DrugSearchResultSchema(BaseModel):
    """Drug search result."""
    drug_name: str
    generic_name: str
    medical_condition: str
    rating: float
    reviews: int
    search_score: float
    search_type: str

class DrugProfileSchema(BaseModel):
    """Complete drug profile from UnifiedDrugSystem."""
    name: str
    basic_info: Optional[Dict[str, Any]] = None
    ai_profile: Optional[Dict[str, Any]] = None
    similar_drugs: List[Any] = []


class SystemStatsSchema(BaseModel):
    """System statistics."""
    total_drugs: int
    medical_conditions: int
    side_effects_tracked: int
    ddi_model_loaded: bool
    drug_profiles_loaded: int
    models_loaded: Dict[str, bool]
    timestamp: str


class ContactRequest(BaseModel):
    """Contact form submission."""
    name: str
    email: str
    subject: str
    message: str

class ToggleSettingRequest(BaseModel):
    """Generic toggle for system settings."""
    key: str
    enabled: bool

class CreateApiKeyRequest(BaseModel):
    """Request to create a new API key."""
    name: str

class LogoutSessionRequest(BaseModel):
    """Request to terminate a session."""
    session_id: int



