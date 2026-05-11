from fastapi import Depends
from app.services.rag_service import RagManager, RagService
from app.services.ai_service import AiService
from app.services.rxnorm_service import RxNormService
from app.services.clinical_service import ClinicalService
from app.services.database_service import DatabaseService
    
from app.services.auth_service import AuthService
from functools import lru_cache

# Singleton-like manager for RAG instances
@lru_cache()
def get_rag_manager() -> RagManager:
    return RagManager()

def get_rag_service(manager: RagManager = Depends(get_rag_manager)) -> RagService:
    return RagService(manager)

@lru_cache()
def get_ai_service() -> AiService:
    return AiService()

@lru_cache()
def get_rxnorm_service() -> RxNormService:
    return RxNormService()

@lru_cache()
def get_clinical_service() -> ClinicalService:
    return ClinicalService()

@lru_cache()
def get_database_service(manager: RagManager = Depends(get_rag_manager)) -> DatabaseService:
    return DatabaseService(manager)


@lru_cache()
def get_auth_service() -> AuthService:
    return AuthService()

def get_unified_drug_system():
    """Return the UnifiedDrugSystem singleton (lazy-loaded via safety_model_service)."""
    from backend.services.safety_model_service import _get_unified
    system = _get_unified()
    if system is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="ML system not available")
    return system
