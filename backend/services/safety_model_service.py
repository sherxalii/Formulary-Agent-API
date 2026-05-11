"""
Drug Safety Service — delegates all ML inference to UnifiedDrugSystem.
UnifiedDrugSystem is the single authoritative loader for all .pkl models.
"""
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

import threading

# ---- Lazy singleton for UnifiedDrugSystem ----
_unified_system = None
_load_lock = threading.Lock()

def _get_unified():
    global _unified_system
    if _unified_system is None:
        with _load_lock:
            if _unified_system is None:
                try:
                    print("\n[INIT] Loading UnifiedDrugSystem Singleton...")
                    from backend.unified_drug_system import UnifiedDrugSystem
                    _unified_system = UnifiedDrugSystem(
                        models_dir='backend/models',
                        datasets_dir='datasets'
                    )
                    logger.info("UnifiedDrugSystem loaded successfully.")
                except Exception as e:
                    logger.error(f"Failed to load UnifiedDrugSystem: {e}")
                    _unified_system = None
    return _unified_system


class DrugSafetyService:
    """
    Thin façade over UnifiedDrugSystem.
    Preserves the original public API so no callers need to change.
    """

    def get_drug_info(self, drug_name: str) -> Optional[Dict]:
        """Return basic drug profile dict or None."""
        unified = _get_unified()
        if unified is None:
            return None
        try:
            profile = unified.get_drug_profile(drug_name)
            return profile.get('basic_info') or profile.get('ai_profile')
        except Exception as e:
            logger.error(f"get_drug_info failed for '{drug_name}': {e}")
            return None

    def check_safety(
        self,
        drug_name: str,
        patient_conditions: List[str] = None,
        patient_allergies: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns a safety report with risks and alternatives.
        Delegates scoring + DDI to UnifiedDrugSystem.
        """
        unified = _get_unified()
        if unified is None:
            return {"status": "error", "message": "ML models not loaded"}

        patient_conditions = patient_conditions or []
        patient_allergies  = patient_allergies  or []

        # Build patient context dict for UnifiedDrugSystem
        patient_ctx = {
            "allergies": patient_allergies,
            "conditions": patient_conditions,
        }

        # Get drug profile to find its medical condition
        try:
            profile     = unified.get_drug_profile(drug_name)
            basic_info  = profile.get('basic_info') or {}
            condition   = basic_info.get('medical_condition', '')
        except Exception:
            condition = ''

        if not condition:
            return {
                "status": "unknown",
                "message": f"Drug '{drug_name}' not found in safety database."
            }

        # Identify risks from allergy / condition conflicts using association rules
        risks = []
        unified_sys = unified  # alias for clarity

        # Use association rules if available (same logic as before, now sourced from unified)
        if unified_sys.rules is not None and unified_sys.drugs_df is not None:
            drug_idx = unified_sys.search_index.get(drug_name.lower())
            if drug_idx is not None and drug_idx < len(unified_sys.drugs_df):
                row = unified_sys.drugs_df.iloc[drug_idx]
                drug_classes = str(row.get('drug_classes', '')).split(',')
                for d_class in drug_classes:
                    d_class = d_class.strip()
                    class_rules = unified_sys.rules[
                        unified_sys.rules['antecedents'].apply(lambda x: d_class in str(x))
                    ]
                    for _, rule in class_rules.iterrows():
                        side_effect = list(rule['consequents'])[0]
                        if patient_allergies and side_effect.lower() in [a.lower() for a in patient_allergies]:
                            risks.append({
                                "type": "allergy",
                                "severity": "high",
                                "message": (
                                    f"Potential allergic reaction: {side_effect}. "
                                    f"Drug class '{d_class}' is associated with this side effect."
                                ),
                            })
                        if patient_conditions and side_effect.lower() in [c.lower() for c in patient_conditions]:
                            risks.append({
                                "type": "condition_conflict",
                                "severity": "medium",
                                "message": (
                                    f"May worsen condition: {side_effect}. "
                                    f"Drug class '{d_class}' has a high correlation with this symptom."
                                ),
                            })

        # K-Means cluster safety check
        if unified_sys.kmeans_model is not None and unified_sys.drugs_df is not None:
            try:
                import pandas as pd
                drug_idx = unified_sys.search_index.get(drug_name.lower())
                if drug_idx is not None and drug_idx < len(unified_sys.drugs_df):
                    row = unified_sys.drugs_df.iloc[drug_idx]
                    input_df = pd.DataFrame(
                        [[row.get('rating', 0), row.get('no_of_reviews', 0)]],
                        columns=['rating', 'no_of_reviews']
                    )
                    cluster = unified_sys.kmeans_model.predict(input_df)[0]
                    if cluster == 0:
                        risks.append({
                            "type": "safety_alert",
                            "severity": "medium",
                            "message": (
                                "This medication is in a low-usage cluster with fewer reviews. "
                                "Monitor closely for unusual side effects."
                            ),
                        })
            except Exception as e:
                logger.warning(f"K-Means check failed: {e}")

        # Suggest alternatives using UnifiedDrugSystem
        alternatives = []
        if risks:
            try:
                raw_alts = unified_sys.get_drug_alternatives(drug_name)
                for alt in raw_alts[:3]:
                    alternatives.append({
                        "drug_name": alt.get('drug_name', ''),
                        "rating": alt.get('rating', 0.0),
                        "reason": (
                            f"High rating ({alt.get('rating', 0):.1f}) and better safety profile "
                            f"for {alt.get('medical_condition', condition)}."
                        ),
                    })
            except Exception as e:
                logger.warning(f"Alternatives lookup failed: {e}")

        return {
            "status": "success",
            "safe": len(risks) == 0,
            "risks": risks,
            "alternatives": alternatives,
            "drug_details": {
                "name": drug_name,
                "class": basic_info.get('drug_classes', ''),
                "condition": condition,
                "rating": basic_info.get('rating', 0),
            },
        }

    def check_ddi_local(self, drugs: List[str]) -> List[Dict[str, Any]]:
        """
        Check Drug-Drug Interactions for a list of drugs using the OpenFDA RF model.
        Returns list of interaction dicts (same format as before).
        """
        unified = _get_unified()
        if unified is None or len(drugs) < 2:
            return []

        interactions = []
        from itertools import combinations

        normalized = [str(d).upper().strip() for d in drugs]

        for d1, d2 in combinations(normalized, 2):
            try:
                warning = unified.check_ddi(d1, d2)
                if warning:
                    prob = warning.confidence
                    severity = 'high' if prob > 0.8 else 'medium'
                    interactions.append({
                        "type": "ddi",
                        "severity": severity,
                        "message": (
                            f"Interaction detected between {d1} and {d2} based on FDA adverse "
                            f"event profiles (Confidence: {prob:.2f}). "
                            f"{warning.recommendation}"
                        ),
                        "drugs": [d1, d2],
                        "risk_level": warning.risk_level.value,
                        "shared_reactions": warning.shared_reactions,
                    })
            except Exception as e:
                logger.warning(f"DDI check failed for {d1}+{d2}: {e}")

        return interactions

    def get_system_stats(self) -> Dict[str, Any]:
        """Expose UnifiedDrugSystem statistics."""
        unified = _get_unified()
        if unified is None:
            return {"status": "error", "message": "System not loaded"}
        return unified.get_statistics()


# Public singleton
safety_service = DrugSafetyService()
