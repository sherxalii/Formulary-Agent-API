import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any
from datetime import datetime

from app.models.schemas import (
    PersonalizedCheckRequest, PersonalizedCheckResponse,
    PatientContext, DrugInfoResponse,
    DDIWarningSchema, DDICheckRequest, DDIBatchRequest,
    RecommendationRequest, DrugRecommendationSchema,
    DrugProfileSchema, SystemStatsSchema,
    SafetyAlert
)
from app.core.dependencies import (
    get_clinical_service, get_rxnorm_service, get_rag_service,
    get_unified_drug_system,
)
from app.services.clinical_service import ClinicalService
from app.services.rxnorm_service import RxNormService
from app.services.rag_service import RagService

router = APIRouter()

# ============================================================================
# EXISTING ENDPOINTS (surface API unchanged)
# ============================================================================

@router.post("/personalized-check", response_model=PersonalizedCheckResponse)
async def personalized_check(
    request: PersonalizedCheckRequest,
    clinical_service: ClinicalService = Depends(get_clinical_service),
    rxnorm_service: RxNormService = Depends(get_rxnorm_service)
):
    """
    Check a list of drugs against a patient's context for safety and interactions.
    Uses local OpenFDA DDI ML model via UnifiedDrugSystem.
    """
    print("\n" + "="*50)
    print(f"🚀 RECEIVED DDI CHECK REQUEST: {len(request.drugs)} drugs")
    print("="*50 + "\n")
    patient = request.patient_context
    if not patient:
        patient = PatientContext()

    drug_identifiers = []
    for d in request.drugs:
        if isinstance(d, str):
            drug_identifiers.append(d)
        else:
            rxcui = d.get('rxcui')
            # If we have a real RXCUI, use it; otherwise use the name (especially for ML_LOCAL)
            if rxcui and rxcui != "ML_LOCAL":
                drug_identifiers.append(str(rxcui))
            else:
                drug_identifiers.append(d.get('drug_name', ''))

    # 1. Prepare and resolve names in parallel if needed
    resolved_names = []
    for d in request.drugs:
        d_name = d if isinstance(d, str) else d.get('drug_name', '')
        rxcui = d.get('rxcui') if isinstance(d, dict) else None
        
        if (not d_name or d_name.isdigit()) and rxcui and rxcui != "ML_LOCAL":
            resolved = rxnorm_service.resolve_rxcui_to_name(str(rxcui))
            if resolved: d_name = resolved
        resolved_names.append(d_name)

    # 2. RUN EVERYTHING IN PARALLEL
    # - Individual safety checks for each drug
    # - Local ML DDI check
    # - Clinical AI DDI check (fallback)
    
    print(f"⚡ STARTING PARALLEL EXECUTION for {len(resolved_names)} drugs...")
    
    # Task list for gather
    safety_tasks = [clinical_service.evaluate_contraindications(name, "", "", patient) for name in resolved_names]
    ddi_local_task = clinical_service.check_ddi_local(resolved_names)
    
    tasks = safety_tasks + [ddi_local_task]
    
    # Add Clinical AI DDI task if there are >= 2 drugs
    if len(resolved_names) >= 2:
        tasks.append(rxnorm_service.get_interactions(resolved_names))
    
    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Extract results from gather
    safety_results = all_results[:len(resolved_names)]
    local_ddi_alerts = all_results[len(resolved_names)] if not isinstance(all_results[len(resolved_names)], Exception) else []
    
    clinical_ddi_alerts = []
    if len(resolved_names) >= 2:
        clinical_res = all_results[-1]
        if not isinstance(clinical_res, Exception):
            for ddi in clinical_res:
                drugs = ddi.get('drugs', [])
                if isinstance(drugs, str):
                    drugs = [d.strip() for d in drugs.split(',')]
                
                clinical_ddi_alerts.append(SafetyAlert(
                    type='ddi',
                    severity=ddi.get('severity', 'high'),
                    message=ddi.get('message', 'Interaction detected'),
                    drugs=drugs
                ))

    # 3. Combine Results
    results = []
    for i, name in enumerate(resolved_names):
        alerts = safety_results[i] if not isinstance(safety_results[i], Exception) else []
        results.append({
            'drug_name': name,
            'alerts': [a.dict() for a in alerts],
            'safe': len(alerts) == 0
        })

    # Combine all DDI alerts
    all_ddi_alerts = local_ddi_alerts + clinical_ddi_alerts
    
    # Link DDI alerts to results
    for interaction in all_ddi_alerts:
        interaction_drugs_normalized = [n.lower() for n in interaction.drugs]
        for res in results:
            res_name_lower = res['drug_name'].lower()
            is_involved = any(n in res_name_lower or res_name_lower in n for n in interaction_drugs_normalized)
            if is_involved:
                if not any(a['message'] == interaction.message for a in res['alerts']):
                    res['alerts'].append(interaction.dict())
                    res['safe'] = False

    print(f"✅ PARALLEL EXECUTION COMPLETE. Total alerts: {sum(len(r['alerts']) for r in results)}")
    return PersonalizedCheckResponse(success=True, results=results)


@router.get("/ddi/search")
async def ddi_search(
    q: str = "",
    rxnorm_service: RxNormService = Depends(get_rxnorm_service),
    unified: Any = Depends(get_unified_drug_system)
):
    """Independent drug search for the DDI tool using Local ML + RxNorm fallback."""
    # 1. Try Local ML Model first (fast & natural language)
    local_results = []
    if unified:
        ml_suggestions = unified.search_drugs(q)
        for sug in ml_suggestions[:10]:
            local_results.append({
                "name": f"{sug.get('drug_name')} ({sug.get('generic_name')})",
                "rxcui": "ML_LOCAL", # We'll resolve this to generic name in DDI check
                "availability": "Local Model"
            })
    
    # 2. Try RxNorm for full coverage
    rx_results = await rxnorm_service.search_drugs(q)
    
    # 3. Merge results, prioritizing Local ML
    combined = local_results
    seen_names = {res['name'].lower() for res in local_results}
    
    for res in rx_results:
        if res['name'].lower() not in seen_names:
            combined.append(res)
            seen_names.add(res['name'].lower())
            
    return {"success": True, "results": combined[:15]}


@router.get("/drugs/{drug_name}", response_model=DrugInfoResponse)
async def get_drug_info(
    drug_name: str,
    rxnorm_service: RxNormService = Depends(get_rxnorm_service)
):
    """Fetch comprehensive drug information from RxNorm."""
    info = await rxnorm_service.get_drug_info(drug_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Drug {drug_name} not found")
    return DrugInfoResponse(success=True, **info)


@router.get("/formulary/check")
async def check_formulary_coverage(
    drug: str,
    plan: str = "",
    rag_service: RagService = Depends(get_rag_service)
):
    """Check insurance coverage for a specific drug."""
    res = await rag_service.search_drug_alternatives(drug, plan)
    return {
        "success": True,
        "covered": res.get("primary_indication") == "INSURED",
        "status": res.get("primary_indication"),
        "drug": drug,
        "plan": plan,
    }


@router.post("/safety-check")
async def safety_check(request: Dict[str, Any]):
    """
    ML safety check for a drug against patient context using UnifiedDrugSystem.
    Input: { "drug_name": "...", "patient_context": { "conditions": [], "allergies": [] } }
    """
    from backend.services.safety_model_service import safety_service

    drug_name = request.get("drug_name")
    if not drug_name:
        raise HTTPException(status_code=400, detail="drug_name is required")

    patient_context = request.get("patient_context", {}) or {}
    conditions = patient_context.get("conditions", [])
    allergies  = patient_context.get("allergies", [])

    report = safety_service.check_safety(drug_name, conditions, allergies)
    return {"success": True, "report": report}


# ============================================================================
# NEW UNIFIED DRUG SYSTEM ENDPOINTS
# ============================================================================

def _warning_to_schema(w) -> DDIWarningSchema:
    """Convert a DDIWarning dataclass → DDIWarningSchema."""
    return DDIWarningSchema(
        drug1=w.drug1,
        drug2=w.drug2,
        risk_level=w.risk_level.value,
        confidence=round(w.confidence, 4),
        shared_reactions=w.shared_reactions or [],
        recommendation=w.recommendation,
    )


@router.post("/ddi/check", tags=["DDI"])
async def check_ddi(
    request: DDICheckRequest,
    unified=Depends(get_unified_drug_system)
):
    """
    Check drug-drug interaction between exactly two drugs.

    **Example:**
    ```json
    { "drug1": "WARFARIN", "drug2": "ASPIRIN" }
    ```
    """
    warning = unified.check_ddi(request.drug1, request.drug2)
    if not warning:
        return {
            "message": "No significant interaction found",
            "drug1": request.drug1,
            "drug2": request.drug2,
            "risk_level": "low",
        }
    return _warning_to_schema(warning).dict()


@router.post("/ddi/batch", tags=["DDI"])
async def check_ddi_batch(
    request: DDIBatchRequest,
    unified=Depends(get_unified_drug_system)
):
    """
    Check one primary drug against a list of other drugs for interactions.

    **Example:**
    ```json
    { "primary_drug": "WARFARIN", "other_drugs": ["ASPIRIN", "IBUPROFEN"] }
    ```
    """
    warnings = unified.check_ddi_batch(request.primary_drug, request.other_drugs)
    return {
        "primary_drug": request.primary_drug,
        "total_drugs_checked": len(request.other_drugs),
        "interactions_found": len(warnings),
        "warnings": [_warning_to_schema(w).dict() for w in warnings],
    }


@router.post("/ddi/add-drug-safety-check", tags=["DDI"])
async def add_drug_safety_check(
    new_drug: str = Query(..., description="Drug you are considering adding"),
    current_medications: List[str] = Query(..., description="Patient's current drug list"),
    unified=Depends(get_unified_drug_system)
):
    """
    Comprehensive safety check before adding a new drug to a patient's regimen.

    **Example:** `/api/ddi/add-drug-safety-check?new_drug=ASPIRIN&current_medications=WARFARIN&current_medications=METFORMIN`
    """
    from backend.unified_drug_system import RiskLevel
    warnings       = unified.check_ddi_batch(new_drug, current_medications)
    critical_count = sum(1 for w in warnings if w.risk_level == RiskLevel.CRITICAL)
    high_count     = sum(1 for w in warnings if w.risk_level == RiskLevel.HIGH)
    safe_to_add    = critical_count == 0

    return {
        "new_drug": new_drug,
        "current_medications": current_medications,
        "safe_to_add": safe_to_add,
        "risk_summary": {
            "critical": critical_count,
            "high": high_count,
            "total_interactions": len(warnings),
        },
        "interactions": [
            {
                "interacting_drug": w.drug2,
                "risk_level": w.risk_level.value,
                "confidence": round(w.confidence, 4),
                "shared_reactions": w.shared_reactions,
                "recommendation": w.recommendation,
            }
            for w in warnings
        ],
        "overall_recommendation": (
            "SAFE TO ADD - No critical interactions detected"
            if safe_to_add
            else "CAUTION REQUIRED - Review interactions with healthcare provider"
        ),
    }


@router.post("/recommendations", response_model=List[DrugRecommendationSchema], tags=["Recommendations"])
async def get_drug_recommendations(
    request: RecommendationRequest,
    unified=Depends(get_unified_drug_system)
):
    """
    Get personalized drug recommendations ranked by confidence score.

    **Example:**
    ```json
    {
        "medical_condition": "hypertension",
        "patient_context": { "age": 55, "pregnancy_status": "not_pregnant", "allergies": ["sulfa"] },
        "current_medications": ["aspirin"],
        "num_recommendations": 5
    }
    ```
    """
    patient_ctx = request.patient_context.dict() if request.patient_context else {}
    recs = unified.get_recommendations(
        medical_condition=request.medical_condition,
        patient_context=patient_ctx,
        current_medications=request.current_medications or [],
        num_recommendations=request.num_recommendations,
    )
    if not recs:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendations found for: {request.medical_condition}"
        )
    return [
        DrugRecommendationSchema(
            drug_name=r.drug_name,
            confidence=round(r.confidence, 4),
            reasoning=r.reasoning,
            side_effects=r.side_effects,
            rating=r.rating,
            reviews=r.reviews,
            ddi_warnings=[_warning_to_schema(w) for w in r.ddi_warnings],
        )
        for r in recs
    ]


@router.get("/drug-profile/{drug_name}", response_model=DrugProfileSchema, tags=["Recommendations"])
async def get_drug_profile(
    drug_name: str,
    unified=Depends(get_unified_drug_system)
):
    """
    Get a comprehensive drug profile: basic info, FDA adverse-event profile,
    and similar drugs ranked by cosine similarity.
    """
    profile = unified.get_drug_profile(drug_name)
    if not profile.get('basic_info') and not profile.get('ai_profile'):
        raise HTTPException(status_code=404, detail=f"Drug not found: {drug_name}")

    # similar_drugs is a list of (name, score) tuples — convert to serialisable dicts
    similar = [
        {"drug": d, "similarity": round(float(s), 4)}
        for d, s in (profile.get('similar_drugs') or [])
    ]
    return DrugProfileSchema(
        name=profile.get('name', drug_name),
        basic_info=profile.get('basic_info'),
        ai_profile=profile.get('ai_profile'),
        similar_drugs=similar,
    )


@router.get("/drug-alternatives/{drug_name}", tags=["Recommendations"])
async def get_drug_alternatives_ml(
    drug_name: str,
    unified=Depends(get_unified_drug_system)
):
    """
    Get ML-ranked alternative drugs for the same medical condition.
    Results are sorted by patient rating.
    """
    alternatives = unified.get_drug_alternatives(drug_name)
    if not alternatives:
        raise HTTPException(
            status_code=404,
            detail=f"No alternatives found for: {drug_name}"
        )
    return {"original_drug": drug_name, "count": len(alternatives), "alternatives": alternatives}


@router.get("/stats", response_model=SystemStatsSchema, tags=["Info"])
async def get_system_stats(unified=Depends(get_unified_drug_system)):
    """
    System statistics: model load status, indexed drug count, conditions tracked.
    """
    stats = unified.get_statistics()
    return SystemStatsSchema(**stats, timestamp=datetime.now().isoformat())
