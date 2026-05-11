import asyncio
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.models.schemas import SearchRequest, SearchResponse, PatientContext
from app.services.database_service import DatabaseService
from app.services.rag_service import RagService
from app.services.clinical_service import ClinicalService
from app.services.rxnorm_service import RxNormService
from app.core.dependencies import get_rag_service, get_clinical_service, get_database_service, get_rxnorm_service
from app.services.cache_service import cache_service
import hashlib
import json

router = APIRouter()

@router.get("/search")
async def quick_search(
    q: str = "",
    db_service: DatabaseService = Depends(get_database_service)
):
    """
    Quick search for drug names (autocomplete) - legacy db search.
    """
    results = await db_service.search_drugs(q)
    return {"success": True, "results": results}

@router.get("/autocomplete")
async def autocomplete_drugs(
    q: str = ""
):
    """
    Real-time autocomplete suggestions using the local ML UnifiedDrugSystem.
    """
    if not q or len(q) < 2:
        return {"success": True, "results": []}
    
    from backend.services.safety_model_service import _get_unified
    unified = _get_unified() # Access the internal unified system for speed
    
    if not unified:
        return {"success": False, "error": "ML system not loaded"}
    
    # Search for drugs by name or generic name
    suggestions = unified.search_drugs(q)
    
    # Format for frontend
    formatted = [{
        "name": s['drug_name'],
        "genericName": s['generic_name'],
        "condition": s['medical_condition'],
        "rating": s['rating']
    } for s in suggestions]
    
    return {"success": True, "results": formatted}

@router.post("/search", response_model=SearchResponse)
async def search_drug_alternatives(
    request: SearchRequest,
    rag_service: RagService = Depends(get_rag_service),
    clinical_service: ClinicalService = Depends(get_clinical_service),
    rxnorm_service: RxNormService = Depends(get_rxnorm_service)
):
    """
    Search for drug alternatives with integrated clinical safety checks.
    """
    # 1. Resolve Patient Context (from request body)
    patient = request.patient_context

    # Create a unique cache key based on the request
    patient_hash = ""
    if patient:
        patient_str = f"{patient.conditions}_{patient.allergies}_{patient.current_medications}_{patient.pregnancy_status}"
        patient_hash = hashlib.md5(patient_str.encode()).hexdigest()
    
    cache_key = f"search_{request.drug_name.lower()}_{request.insurance_name}_{patient_hash}"
    cached_results = cache_service.get(cache_key)
    if cached_results:
        return SearchResponse(**cached_results)

    # 2 & 3. Run RAG search and ML initial safety check in parallel
    from backend.services.safety_model_service import safety_service
    conditions = patient.conditions if patient else []
    allergies = patient.allergies if patient else []
    
    # Create tasks for parallel execution
    rag_task = asyncio.create_task(rag_service.search_drug_alternatives(
        request.drug_name, 
        request.insurance_name,
        patient_context=patient
    ))
    
    # ML check is sync in many parts, so we run it in a thread to not block the event loop
    ml_report_task = asyncio.to_thread(
        safety_service.check_safety, 
        request.drug_name, 
        conditions, 
        allergies
    )
    
    # Wait for both core search paths to complete
    results, ml_report = await asyncio.gather(rag_task, ml_report_task)
    
    if not results.get("success"):
        raise HTTPException(status_code=400, detail=results.get("error", "Search failed"))

    # 4. Integrate Results
    verified_alternatives = []
    
    if ml_report and ml_report.get("status") == "success":
        ml_alts = ml_report.get("alternatives", [])
        for malt in ml_alts:
            malt_name = malt.get("drug_name", "").lower()
            if not malt_name:
                continue
                
            # Check if this drug is already in our results list
            exists = False
            for existing in results.get("alternatives", []):
                existing_name = ""
                if hasattr(existing, 'drug_name'):
                    existing_name = existing.drug_name.lower()
                elif isinstance(existing, dict):
                    existing_name = existing.get('drug_name', '').lower()
                
                if existing_name == malt_name:
                    exists = True
                    break
            
            if not exists:
                alt_obj = {
                    "drug_name": malt.get("drug_name"),
                    "rating": malt.get("rating", 0.0),
                    "recommendation": malt.get("reason", "ML Suggested Alternative")
                }
                if "alternatives" not in results:
                    results["alternatives"] = []
                results["alternatives"].append(alt_obj)

    # 3b. Evaluate all alternatives in parallel for speed
    if patient and results.get("alternatives"):
        # Create a list of tasks for parallel execution
        tasks = [
            clinical_service.evaluate_alternative_safely(alt, patient, rxnorm_service)
            for alt in results["alternatives"]
        ]
        
        # Execute all evaluations concurrently
        verified_alternatives = await asyncio.gather(*tasks)
        
        # 3c. Sort by ML Safety Score (Descending) so Safest is first
        verified_alternatives.sort(key=lambda x: getattr(x, 'safety_score', 0), reverse=True)
        
        results["alternatives"] = verified_alternatives
        
        # Add a summary note about safety
        safe_count = len([a for a in verified_alternatives if getattr(a, 'safe', False)])
        best_alt = verified_alternatives[0].drug_name if verified_alternatives else "None"
        results["patient_safety_summary"] = (
            f"Evaluated {len(verified_alternatives)} alternatives. "
            f"Found {safe_count} safe options. Safest Recommended Alternative: {best_alt}."
        )

    response = SearchResponse(**results)
    # Cache the fully resolved dictionary representation
    cache_service.set(cache_key, response.model_dump())
    
    return response

