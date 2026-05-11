from typing import List, Dict, Any, Optional
import os
import logging
from backend.rxnorm_api import RxNormAPI, TherapeuticClassFilter
from app.core.config import settings
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

class RxNormService:
    def __init__(self):
        self.api = RxNormAPI(rate_limit_delay=0.2)
        self.filter = TherapeuticClassFilter(self.api)

    async def get_drug_info(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """Fetch comprehensive drug information from RxNorm API."""
        cache_key = f"rx_info_{drug_name.lower()}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        try:
            rx_response = self.api.find_rxcui_by_name(drug_name)
            if not rx_response:
                return None
            
            rxcui = rx_response[0]
            # In a real production app, we would fetch more details.
            # For now, we mimic the existing logic.
            result = {
                "name": drug_name,
                "rxcui": rxcui,
                "atc_code": self.api.get_drug_classes_by_rxcui(rxcui, "ATC")
            }
            cache_service.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Error in RxNormService.get_drug_info: {e}")
            return None

    async def get_corrected_name(self, drug_name: str) -> str:
        """Get corrected drug name using spelling suggestions."""
        cache_key = f"rx_corr_{drug_name.lower()}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        result = self.api.get_corrected_drug_name(drug_name)
        cache_service.set(cache_key, result)
        return result

    async def filter_alternatives(self, search_drug: str, alternatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter alternatives by therapeutic class matching."""
        return self.filter.filter_alternatives_by_therapeutic_class(search_drug, alternatives)

    async def get_therapeutic_class(self, drug_name: str) -> Optional[Dict[str, Any]]:
        """Get therapeutic class information for a drug."""
        return self.api.get_therapeutic_class(drug_name)

    def resolve_rxcui_to_name(self, rxcui: str) -> Optional[str]:
        """Robustly resolve an RXCUI to a human-readable drug name."""
        # Try RxNorm Name first (most common)
        info = self.api._make_request(f"/REST/rxcui/{rxcui}/property.json", {"propName": "RxNorm Name"})
        if info and 'propConceptGroup' in info:
            props = info['propConceptGroup'].get('propConcept', [])
            if props and props[0].get('propValue'):
                return props[0].get('propValue')
                
        # Try Prescribable Name
        info = self.api._make_request(f"/REST/rxcui/{rxcui}/property.json", {"propName": "Prescribable Name"})
        if info and 'propConceptGroup' in info:
            props = info['propConceptGroup'].get('propConcept', [])
            if props and props[0].get('propValue'):
                return props[0].get('propValue')
                
        # Fallback to all properties and find any valid name
        info = self.api._make_request(f"/REST/rxcui/{rxcui}/allProperties.json", {"prop": "all"})
        if info and 'propConceptGroup' in info:
            props = info['propConceptGroup'].get('propConcept', [])
            for p in props:
                if p.get('propName') in ['RxNorm Name', 'Full Name', 'Synonym', 'Prescribable Name', 'Brand Name'] and p.get('propValue'):
                    return p.get('propValue')
                    
        return None

    async def search_drugs(self, query: str) -> List[Dict[str, Any]]:
        """Search RxNorm for drug suggestions and prettify names."""
        results = self.api.search_drug_names(query)
        
        # If no direct results, try approximate matches
        if not results:
            logger.info(f"No direct results for '{query}', trying approximate matches...")
            approx_results = self.api.get_approximate_matches(query)
            if approx_results:
                for approx in approx_results[:10]:
                    rxcui = approx.get('rxcui')
                    name = approx.get('name')
                    
                    if not name and rxcui:
                        # Fallback: Get name from properties if missing in candidate
                        name = self.resolve_rxcui_to_name(rxcui)
                    
                    if name and rxcui:
                        results.append({'name': name, 'rxcui': rxcui})
        
        # Deduplicate and format
        seen = set()
        candidates = []
        for r in results:
            name = r.get('name')
            rxcui = r.get('rxcui')
            if name and name not in seen:
                seen.add(name)
                candidates.append({
                    'raw_name': name,
                    'rxcui': rxcui
                })
        
        if not candidates:
            return []

        # Prettify the top candidates using AI
        return await self.prettify_drug_names(candidates[:10])

    async def prettify_drug_names(self, candidates: List[Dict]) -> List[Dict]:
        """Use AI to distill raw RxNorm names into clean clinical names."""
        from langchain_openai import ChatOpenAI
        import json
        import hashlib
        
        # Create a unique key for this set of candidates
        raw_names = sorted([c['raw_name'] for c in candidates])
        names_str = "|".join(raw_names)
        cache_key = f"prettify_{hashlib.md5(names_str.encode()).hexdigest()}"
        
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        try:
            llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, api_key=settings.OPENAI_API_KEY)
            
            names_to_clean = [c['raw_name'] for c in candidates]
            prompt = f"""
            Distill these raw RxNorm drug strings into clean, concise, and readable clinical names.
            Format: [Brand Name (if any)] ([Ingredients + Strengths]) [Form]
            
            Rules:
            1. Remove curly braces, complex pack notations, and strength ratios from the brand name (e.g., remove "20;500;500" from "Voquezna 14 Day TriplePak 20;500;500").
            2. If it's a combination, list ingredients with strengths inside parentheses.
            3. Ensure the clinical form (e.g., Oral Tablet, Injection) is at the end.
            4. If the generic name is already in the brand name, don't repeat it in parentheses.
            5. Keep the output extremely professional, clean, and concise. No raw API artifacts.
            
            Example: "{{100 (acetaminophen 250 MG / aspirin 250 MG / caffeine 65 MG Oral Tablet [Excedrin])}}" -> "Excedrin (Acetaminophen 250mg / Aspirin 250mg / Caffeine 65mg) Oral Tablet"
            Example: "Voquezna 14 Day TriplePak 20;500;500 (amoxicillin 500 MG / clarithromycin 500 MG / vonoprazan 20 MG) Oral Tablet" -> "Voquezna 14 Day TriplePak (Amoxicillin 500mg / Clarithromycin 500mg / Vonoprazan 20mg) Oral Tablet"
            Example: "Aspirin 325 MG Oral Tablet" -> "Aspirin 325mg Oral Tablet"
            
            Raw Strings:
            {json.dumps(names_to_clean, indent=2)}
            
            Return a JSON list of strings in the exact same order.
            Respond ONLY with the JSON array.
            """

            
            res = await llm.ainvoke(prompt)
            content = res.content.strip()
            if content.startswith('```json'): content = content[7:-3].strip()
            elif content.startswith('```'): content = content[3:-3].strip()
            
            clean_names = json.loads(content)
            
            formatted = []
            for i, cand in enumerate(candidates):
                # Use cleaned name if available and not empty, otherwise fallback to raw name
                name = clean_names[i] if (i < len(clean_names) and clean_names[i]) else cand['raw_name']
                formatted.append({
                    'name': name,
                    'rxcui': cand['rxcui'],
                    'availability': 'General Database'
                })
            
            cache_service.set(cache_key, formatted)
            return formatted
        except Exception as e:
            logger.error(f"Failed to prettify drug names: {e}")
            # Fallback to raw names
            return [{
                'name': c['raw_name'],
                'rxcui': c['rxcui'],
                'availability': 'General Database'
            } for c in candidates]

    async def get_interactions(self, drugs: List[str]) -> List[Dict[str, Any]]:
        """
        Check for DDI using OpenAI (Trusted Clinical Source) as NLM Interaction API is discontinued.
        Includes caching to improve performance.
        """
        if len(drugs) < 2:
            return []
            
        from langchain_openai import ChatOpenAI
        import json
        import hashlib
        
        # Create a cache key based on sorted drug list
        drugs_sorted = sorted([str(d).lower() for d in drugs])
        cache_key = f"ddi_{hashlib.md5('|'.join(drugs_sorted).encode()).hexdigest()}"
        
        cached = cache_service.get(cache_key)
        if cached:
            print(f"🎯 CACHE HIT for DDI: {drugs_sorted}")
            return cached

        print(f"🌐 CACHE MISS for DDI: {drugs_sorted}. Calling OpenAI...")

        # Ensure we have drug names for OpenAI, not just RXCUIs
        resolved_names = []
        for drug in drugs:
            if drug.isdigit():
                # Resolve RXCUI to name
                name = self.resolve_rxcui_to_name(drug)
                if name:
                    resolved_names.append(f"{name} (RXCUI: {drug})")
                else:
                    resolved_names.append(f"Drug with RXCUI {drug}")
            else:
                resolved_names.append(drug)

        try:
            llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, api_key=settings.OPENAI_API_KEY)
            
            prompt = f"""
            As a clinical pharmacist, identify all potential drug-drug interactions between these medications:
            {', '.join(resolved_names)}
            
            For each interaction found, provide:
            1. "severity": "high", "medium", or "low"
            2. "message": Concise clinical explanation of the risk and mechanism.
            3. "drugs": A list of the two drugs involved (e.g., ["DRUG1", "DRUG2"]).
            
            Respond with a JSON object: {{"interactions": [...]}}
            Respond ONLY with the JSON object. If no interactions are found, return {{"interactions": []}}.
            """
            
            res = await llm.ainvoke(prompt)
            content = res.content.strip()
            if content.startswith('```json'): content = content[7:-3].strip()
            elif content.startswith('```'): content = content[3:-3].strip()
            
            data = json.loads(content)
            interactions = data.get('interactions', [])
            
            # Sanitize: ensure 'drugs' is always a list
            for interaction in interactions:
                if 'drugs' in interaction and isinstance(interaction['drugs'], str):
                    interaction['drugs'] = [d.strip() for d in interaction['drugs'].split(',')]
            
            cache_service.set(cache_key, interactions)
            return interactions
        except Exception as e:
            logger.error(f"OpenAI Interaction check failed: {e}")
            return []
