import os
import time
import threading
import logging
import asyncio
import re
from typing import Dict, Tuple, Optional, List, Any
from backend.formulary_drug_rag import FormularyDrugRAG
from app.core.config import settings
from app.models.schemas import DrugAlternative, SafetyAlert, PatientContext

logger = logging.getLogger(__name__)

class RagManager:
    """Manages cached RAG instances for different insurance databases."""
    def __init__(self):
        self._instances: Dict[str, Tuple[FormularyDrugRAG, float]] = {}
        self._lock = threading.Lock()

    def get_instance(self, db_name: str, vectorstore_path: str) -> Optional[FormularyDrugRAG]:
        with self._lock:
            cache_key = f"{db_name}::{vectorstore_path}"
            current_time = time.time()
            
            if cache_key in self._instances:
                instance, cached_mtime = self._instances[cache_key]
                try:
                    db_mtime = os.path.getmtime(vectorstore_path)
                    if cached_mtime >= db_mtime:
                        return instance
                    else:
                        del self._instances[cache_key]
                except Exception:
                    del self._instances[cache_key]
            
            try:
                instance = FormularyDrugRAG(
                    openai_api_key=settings.OPENAI_API_KEY,
                    chroma_persist_directory=vectorstore_path,
                    model_name=settings.OPENAI_MODEL_NAME,
                    embedding_model=settings.OPENAI_EMBEDDING_MODEL,
                    enable_ai_enhancement=True,
                    enable_llm_prevalidation=True,
                    auto_cleanup=True
                )
                
                if not instance.load_existing_vectorstore():
                    return None
                
                instance.setup_rag_chain()
                
                try:
                    db_mtime = os.path.getmtime(vectorstore_path)
                except Exception:
                    db_mtime = current_time
                    
                self._instances[cache_key] = (instance, db_mtime)
                return instance
            except Exception as e:
                logger.error(f"Failed to create RAG instance for {db_name}: {e}")
                return None

    def clear(self):
        with self._lock:
            self._instances.clear()

    def get_cache_stats(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"database_name": key.split("::")[0], "cache_timestamp": mtime}
                for key, (_, mtime) in self._instances.items()
            ]

class RagService:
    def __init__(self, manager: RagManager):
        self.manager = manager

    def normalize_name(self, name: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]', '', str(name)).lower()

    def find_matching_database(self, insurance_name: str) -> Tuple[Optional[str], Optional[str]]:
        if not os.path.exists(settings.DATABASE_DIR):
            return None, None
            
        normalized_input = self.normalize_name(insurance_name)
        if not normalized_input:
            return None, None
            
        db_dirs = [d for d in os.listdir(settings.DATABASE_DIR)
                  if os.path.isdir(os.path.join(settings.DATABASE_DIR, d)) and not d.startswith('.')]
        
        normalized_db_map = {self.normalize_name(d): d for d in db_dirs}
        
        if normalized_input in normalized_db_map:
            db_dir = normalized_db_map[normalized_input]
            return db_dir, str(settings.DATABASE_DIR / db_dir)
            
        for norm_db_name, actual_db_dir in normalized_db_map.items():
            if normalized_input in norm_db_name or norm_db_name in normalized_input:
                return actual_db_dir, str(settings.DATABASE_DIR / actual_db_dir)
                
        return None, None

    async def search_drug_alternatives(self, drug_name: str, insurance_name: str, patient_context: Optional[PatientContext] = None) -> Dict[str, Any]:
        """
        Advanced search logic with exact match detection and form splitting.
        """
        start_time = time.time()
        db_name, vectorstore_path = self.find_matching_database(insurance_name)
        
        if not db_name:
            return {"success": False, "error": f"No database found for insurance: {insurance_name}"}
            
        rag = self.manager.get_instance(db_name, vectorstore_path)
        if not rag:
            return {"success": False, "error": f"Failed to load RAG system for {insurance_name}"}

        # Prepare context for RAG if patient info is available
        search_query = drug_name
        if patient_context:
            context_parts = []
            if patient_context.conditions:
                context_parts.append(f"conditions: {', '.join(patient_context.conditions)}")
            if patient_context.allergies:
                context_parts.append(f"allergies: {', '.join(patient_context.allergies)}")
            if patient_context.pregnancy_status != 'not_pregnant':
                context_parts.append(f"status: {patient_context.pregnancy_status}")
            if patient_context.age_group:
                context_parts.append(f"age group: {patient_context.age_group}")
            
            if context_parts:
                search_query = f"{drug_name} for a patient with {'; '.join(context_parts)}"

        is_exact = False
        exact_matches = []
        if hasattr(rag, 'drug_database'):
            orig_lower = drug_name.lower().strip()
            for ingredient, drugs in rag.drug_database.items():
                for d in drugs:
                    if orig_lower == d.get('drug_name', '').lower().strip() or \
                       orig_lower == d.get('generic_name', '').lower().strip():
                        is_exact = True
                        exact_matches.append(d)
        
        # 2. Optimization: If it's an exact match AND there's NO patient context, return instantly!
        if is_exact and not patient_context:
            return {
                "success": True,
                "primary_indication": "INSURED",
                "alternatives": [], # No alternatives needed if original is covered and no safety concerns
                "response_time_ms": round((time.time() - start_time) * 1000, 2),
                "rxnorm_validation_message": "Original medicine already in formulary - no alternatives needed"
            }

        # 3. Otherwise, run the full search (required for alternatives or safety checking)
        enhanced_results = await asyncio.to_thread(rag.find_drug_alternatives, search_query)
        
        # Merge exact match detection from RAG
        is_exact = is_exact or enhanced_results.get('is_exact_match', False)
            

        # 3. Process Alternatives (with form splitting)
        raw_alternatives = enhanced_results.get("formulary_alternatives", [])
        processed_alternatives = []
        
        for alt in raw_alternatives:
            d_name = alt.get('drug_name', '')
            g_name = alt.get('generic_name', '')
            m_form_raw = alt.get('medicine_form', alt.get('dosage_form', ''))
            t_class = alt.get('therapeutic_class', '')
            
            # Split forms by '|' as in legacy code
            forms = [f.strip() for f in str(m_form_raw).split('|')] if m_form_raw else ['']
            
            for f in forms:
                if f or len(forms) == 1:
                    processed_alternatives.append(DrugAlternative(
                        drug_name=d_name,
                        generic_name=g_name,
                        medicine_form=f,
                        therapeutic_class=t_class
                    ))

        return {
            "success": True,
            "primary_indication": "INSURED" if is_exact else "NOT INSURED",
            "alternatives": processed_alternatives,
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "rxnorm_validation": enhanced_results.get('therapeutic_filtering_applied', False),
            "rxnorm_validation_message": "Alternatives generated considering patient context" if patient_context else enhanced_results.get('rxnorm_validation_message'),
            "name_corrected": enhanced_results.get('name_corrected', False),
            "corrected_drug_name": enhanced_results.get('corrected_drug_name')
        }

    async def get_database_summary(self, database_id: str) -> Dict[str, Any]:
        """Fetch database summary from RAG instance."""
        db_dir, vectorstore_path = self.find_matching_database(database_id)
        if not db_dir:
            return {"success": False, "error": "Database not found"}
            
        rag = self.manager.get_instance(db_dir, vectorstore_path)
        if not rag:
            return {"success": False, "error": "Failed to load database"}
            
        summary = rag.get_database_summary()
        return {"success": True, "summary": summary}
