import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.models.schemas import PatientContext, SafetyAlert, DrugAlternative
from backend.services.safety_model_service import safety_service
    
logger = logging.getLogger(__name__)

class ClinicalService:
    def __init__(self):
        self.severity_map = {'high': 3, 'medium': 2, 'low': 1}


    async def check_ddi_local(self, drugs: List[str]) -> List[SafetyAlert]:
        """Check for DDI using local OpenFDA ML model."""
        if len(drugs) < 2:
            return []
            
        alerts = []
        try:
            local_interactions = safety_service.check_ddi_local(drugs)
            for ddi in local_interactions:
                alerts.append(SafetyAlert(
                    type='ddi',
                    severity=ddi.get('severity', 'high'),
                    message=ddi.get('message', 'Potential interaction detected'),
                    drugs=ddi.get('drugs', [])
                ))
        except Exception as e:
            logger.error(f"Local DDI check failed: {e}")
            
        return alerts


    async def evaluate_contraindications(self, drug_name: str, generic_name: str, drug_class: str, patient: PatientContext) -> List[SafetyAlert]:
        """
        Evaluate contraindications for a single drug against patient context.
        Now uses ML and OpenAI for real-time verification in parallel.
        """
        alerts = []
        d_full_name = f"{drug_name} ({generic_name})" if generic_name else drug_name
        
        # 1. Start OpenAI Clinical Validation as an async task
        ai_task = asyncio.create_task(self.openai_evaluate_safety(d_full_name, drug_class, patient))
        
        # 2. Perform ML-Based Safety Check (Internal Model) - happens while OpenAI is processing
        try:
            ml_report = safety_service.check_safety(
                drug_name or generic_name, 
                patient.conditions, 
                patient.allergies
            )
            
            if ml_report.get("status") == "success":
                for risk in ml_report.get("risks", []):
                    alerts.append(SafetyAlert(
                        type=risk['type'],
                        severity=risk['severity'],
                        message=risk['message']
                    ))
        except Exception as e:
            logger.error(f"ML Safety Check failed: {e}")

        # 3. Wait for OpenAI Clinical Validation to complete
        ai_alerts = await ai_task
        alerts.extend(ai_alerts)

        return alerts

    async def openai_evaluate_safety(self, drug_name: str, drug_class: str, patient: PatientContext) -> List[SafetyAlert]:
        """Use OpenAI to evaluate safety against patient context with caching."""
        from langchain_openai import ChatOpenAI
        from app.core.config import settings
        from app.services.cache_service import cache_service
        import json
        import hashlib
        
        # Create a cache key based on drug and patient context
        patient_str = f"{sorted(patient.conditions)}|{sorted(patient.allergies)}|{patient.pregnancy_status}|{patient.age_group}"
        cache_key = f"safety_{drug_name}_{drug_class}_{hashlib.md5(patient_str.encode()).hexdigest()}".lower().replace(" ", "_")
        
        cached = cache_service.get(cache_key)
        if cached:
            print(f"CACHE HIT for safety check: {drug_name}")
            return [SafetyAlert(**a) for a in cached]

        print(f"CACHE MISS for safety check: {drug_name}. Calling OpenAI...")

        try:
            llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, api_key=settings.OPENAI_API_KEY)
            prompt = f"""
            As a clinical pharmacist, evaluate the safety of {drug_name} (Class: {drug_class}) for this patient:
            - Conditions: {', '.join(patient.conditions)}
            - Allergies: {', '.join(patient.allergies)}
            - Pregnancy Status: {patient.pregnancy_status}
            - Alcohol Use: {patient.alcohol_use}
            - Age Group: {patient.age_group}
            
            Identify any contraindications or major safety risks.
            Provide a JSON list of objects with:
            1. "type": one of ["allergy", "condition", "warning"]
            2. "severity": one of ["high", "medium", "low"]
            3. "message": clear clinical warning message.
            
            Return ONLY the JSON array (empty if no risks found).
            """
            res = await llm.ainvoke(prompt)
            content = res.content.strip()
            if content.startswith('```json'): content = content[7:-3].strip()
            elif content.startswith('```'): content = content[3:-3].strip()
            
            data = json.loads(content)
            cache_service.set(cache_key, data) # Cache the raw dicts
            return [SafetyAlert(**a) for a in data]
        except Exception as e:
            logger.error(f"OpenAI safety evaluation failed: {e}")
            return []

    async def evaluate_alternative_safely(self, alternative: Any, patient: PatientContext, rxnorm_service: Any) -> DrugAlternative:
        """Evaluate an alternative drug against patient context and current meds."""
        if not patient:
            if isinstance(alternative, DrugAlternative): return alternative
            return DrugAlternative(**alternative) if isinstance(alternative, dict) else alternative
 
        # Convert dict to DrugAlternative if needed
        if isinstance(alternative, dict):
            alt_obj = DrugAlternative(
                drug_name=alternative.get('drug_name', ''),
                generic_name=alternative.get('generic_name', ''),
                medicine_form=alternative.get('medicine_form', ''),
                therapeutic_class=alternative.get('therapeutic_class', '')
            )
            alt_obj.rating = alternative.get('rating', 0.0)
        else:
            alt_obj = alternative
 
        # 1. Check Contraindications (ML + OpenAI)
        alerts = await self.evaluate_contraindications(
            alt_obj.drug_name, 
            alt_obj.generic_name, 
            alt_obj.therapeutic_class, 
            patient
        )
        
        # 2. Check DDI (Local OpenFDA ML Model)
        all_meds = patient.current_medications + [alt_obj.drug_name]
        ddi_alerts = await self.check_ddi_local(all_meds)
        for ddi in ddi_alerts:
            if any(alt_obj.drug_name.lower() in d.lower() for d in ddi.drugs):
                alerts.append(ddi)
 
        # 3. Calculate Advanced Metrics
        alt_obj.safety_alerts = alerts
        alt_obj.risk_score = sum(self.severity_map.get(a.severity, 0) for a in alerts)
        
        # Safety Score calculation
        base_score = 100
        for alert in alerts:
            if alert.severity == 'high': base_score -= 40
            elif alert.severity == 'medium': base_score -= 20
            else: base_score -= 10
        alt_obj.safety_score = max(0, base_score)
        
        # Pregnancy Safety
        alt_obj.pregnancy_safe = not any(a.type == 'condition' and 'pregnancy' in a.message.lower() for a in alerts)
        
        alt_obj.safe = (alt_obj.risk_score == 0)
        
        # If rating wasn't set, provide a default based on safety
        if alt_obj.rating == 0.0:
            alt_obj.rating = round(alt_obj.safety_score / 20, 1)
            
        return alt_obj

clinical_service = ClinicalService()

