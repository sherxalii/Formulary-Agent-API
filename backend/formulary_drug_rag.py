import os
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json
import difflib
import PyPDF2
import pdfplumber
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import hashlib
from functools import lru_cache
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Import BM25 for hybrid search
try:
    from langchain_community.retrievers import BM25Retriever
    from langchain_classic.retrievers import EnsembleRetriever
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    
from .pdf_processor import EnhancedPDFProcessor
from .medical_processor import MedicalTextProcessor
from .medicine_forms_master_list import MedicineFormsMaster

# Import Pydantic models for robust data validation and LLM structured outputs
try:
    from .medicine_models import MedicineEntry, MedicineList, MedicineExtractionResponse
    PYDANTIC_AVAILABLE = True
    # print("Pydantic models loaded - structured LLM outputs enabled")
except ImportError:
    PYDANTIC_AVAILABLE = False
    # print("Pydantic models not available - using legacy validation")

# Set up logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class FormularyDrugRAG:
    """
    RAG system for Formulary documents with drug alternative finding,
    active ingredient matching, and cost tier analysis.
    """

    def __init__(self,
                 openai_api_key: str,
                 chroma_persist_directory: str = os.path.join("database", "formulary_chroma_db"),
                 model_name: str = "gpt-4o-mini",
                 embedding_model: str = "text-embedding-3-large",
                 enable_ai_enhancement: bool = True,
                 enable_completion_api: bool = True,  # NEW: Disable completion API calls for faster responses
                 enable_llm_prevalidation: bool = True,  # NEW: Enable LLM pre-validation before embedding
                 auto_cleanup: bool = True,  # NEW: Automatically clean up invalid entries after database creation
                 cache_size: int = 1000,
                 max_workers: int = 8):
        """
        Initialize the Formulary Drug RAG system.
        
        Args:
            enable_ai_enhancement: If False, will use knowledge base only for faster processing
            enable_completion_api: If False, skip expensive completion API calls (no descriptions)
            enable_llm_prevalidation: If True, use LLM to validate medicines before creating embeddings
            auto_cleanup: If True, automatically clean up invalid entries after database creation
            cache_size: Maximum number of cached search results
            max_workers: Maximum number of threads for parallel processing
        """
        self.openai_api_key = openai_api_key
        os.environ["OPENAI_API_KEY"] = openai_api_key
        self.enable_ai_enhancement = enable_ai_enhancement
        self.enable_completion_api = enable_completion_api  # NEW: Store completion API setting
        self.enable_llm_prevalidation = enable_llm_prevalidation  # NEW: Store LLM pre-validation setting
        self.auto_cleanup = auto_cleanup  # NEW: Store auto cleanup setting
        self.cache_size = cache_size
        self.max_workers = max_workers
        self.chroma_persist_directory = chroma_persist_directory
        
        # Persistent cache path
        self.cache_file = os.path.join(self.chroma_persist_directory, "search_cache.json")

        # Initialize components
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # Initialize standard LLM for text responses
        self.llm = ChatOpenAI(
            model=model_name, 
            temperature=0, 
            request_timeout=180, 
            max_retries=5
        )
        
        # Use the same instance for text responses - no need for separate instance
        self.llm_text = self.llm
        
        # Initialize structured LLM with version compatibility
        self.structured_llm = None
        if PYDANTIC_AVAILABLE:
            try:
                # Try modern LangChain structured output approach
                self.structured_llm = self.llm.with_structured_output(MedicineExtractionResponse, method="function_calling")
                # print("LLM configured with modern structured outputs")
            except AttributeError as e:
                # print(f"Modern structured output not available: {e}")
                # Fall back to JSON mode for older LangChain versions
                try:
                    self.structured_llm = ChatOpenAI(
                        model=model_name, 
                        temperature=0, 
                        request_timeout=180, 
                        max_retries=5,
                        model_kwargs={"response_format": {"type": "json_object"}}
                    )
                    # print("LLM configured with JSON response format fallback")
                except Exception as fallback_error:
                    # print(f"Both structured output methods failed: {fallback_error}")
                    self.structured_llm = None
            except Exception as e:
                # print(f"Failed to create structured LLM: {e}")
                self.structured_llm = None
        else:
            # print("Pydantic models not available - structured outputs disabled")
            pass
        self.vectorstore = None
        self.retriever = None
        self.hybrid_retriever = None  # Hybrid retriever combining semantic + BM25
        self.rag_chain = None
        self.chroma_persist_directory = chroma_persist_directory

        # NEW: Timeout and retry configuration
        self.chunk_timeout_seconds = 180  # 3 minutes per chunk
        self.max_chunk_retries = 3  # Retry failed chunks
        self.chunk_size_for_extraction = 3000  # Reduced from 6000 to avoid timeouts
        self.max_extraction_workers = 2  # Reduced parallel workers to avoid rate limits

        # Store processed documents metadata
        self.processed_documents = {}
        self.drug_database = {}  # Will store structured drug data
        self.raw_text_content = ""  # Store raw PDF text for debugging
        self.all_drug_names = []  # Cache for autocomplete suggestions
        
        # Performance optimization caches
        self.search_cache = {}  # Cache for search results
        self.embedding_cache = {}  # Cache for embedding results
        self.similarity_cache = {}  # Cache for similarity calculations
        self.cache_timestamps = {}  # Timestamps for cache expiration
        self.cache_expiry = timedelta(hours=1)  # Cache expires after 1 hour
        self._cache_lock = threading.Lock()  # Thread-safe cache access
        
        # Dynamic dosage form extraction and caching
        self.dynamic_dosage_forms = []  # Dynamically extracted dosage forms
        self.dosage_forms_cache = {}  # Cache dosage forms per PDF
        self.current_pdf_path = None  # Track current PDF for dosage form extraction
        
        # Initialize master medicine forms list
        self.medicine_forms_master = MedicineFormsMaster()
        self.comprehensive_forms_list = MedicineFormsMaster.get_all_forms()
        
        # Pre-computed common search patterns
        self.common_patterns = {}
        self.exact_match_cache = {}  # Cache for exact matches
        
        # Thread pool for parallel processing
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        
        # Initialize enhanced processors
        self.enhanced_pdf_processor = None
        self.medical_processor = MedicalTextProcessor()

        # Optimized text splitter for drug entries - each drug should be its own chunk
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,  # Smaller chunks for individual drug entries
            chunk_overlap=50,  # Minimal overlap since each drug is separate
            length_function=len,
            separators=["|", "\n\n", "\n", ".", " "]  # Split on drug separators first
        )

        # Load persistent cache
        self._load_cache_from_disk()

        self._setup_prompt_template()
    
    def __del__(self):
        """Cleanup thread pool on destruction."""
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=False)        
        
    def _get_cache_key(self, *args) -> str:
        """Generate a cache key from arguments."""
        return hashlib.md5(str(args).encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid."""
        if cache_key not in self.cache_timestamps:
            return False
        return datetime.now() - self.cache_timestamps[cache_key] < self.cache_expiry
    
    def _get_from_cache(self, cache_dict: dict, cache_key: str):
        """Get value from cache if valid."""
        with self._cache_lock:
            if cache_key in cache_dict and self._is_cache_valid(cache_key):
                return cache_dict[cache_key]
            return None
    
    def _set_cache(self, cache_dict: dict, cache_key: str, value):
        """Set value in cache with timestamp."""
        with self._cache_lock:
            # Implement LRU-like behavior by removing old entries
            if len(cache_dict) >= self.cache_size:
                # Remove oldest entry
                oldest_key = min(self.cache_timestamps.keys(), 
                               key=lambda k: self.cache_timestamps[k])
                cache_dict.pop(oldest_key, None)
                self.cache_timestamps.pop(oldest_key, None)
            
            cache_dict[cache_key] = value
            self.cache_timestamps[cache_key] = datetime.now()
            
            # Save to disk if it's the search cache
            if cache_dict == self.search_cache:
                self._save_cache_to_disk()

    def _load_cache_from_disk(self):
        """Load search cache from disk."""
        if not os.path.exists(self.cache_file):
            return
            
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.search_cache = data.get('search_cache', {})
                # Restore timestamps as now to avoid immediate expiration
                for key in self.search_cache:
                    self.cache_timestamps[key] = datetime.now()
            # print(f"Loaded {len(self.search_cache)} cached searches from disk")
        except Exception as e:
            print(f"Failed to load cache from disk: {e}")

    def _save_cache_to_disk(self):
        """Save search cache to disk."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump({'search_cache': self.search_cache}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save cache to disk: {e}")
    
    def _clear_expired_cache(self):
        """Clear expired cache entries."""
        with self._cache_lock:
            current_time = datetime.now()
            expired_keys = [
                key for key, timestamp in self.cache_timestamps.items()
                if current_time - timestamp > self.cache_expiry
            ]
            
            for key in expired_keys:
                self.search_cache.pop(key, None)
                self.embedding_cache.pop(key, None)
                self.similarity_cache.pop(key, None)
                self.cache_timestamps.pop(key, None)

    def _setup_prompt_template(self):
        
        """Set up the prompt template for formulary drug queries."""
        self.prompt_template = ChatPromptTemplate.from_template("""
You are an expert pharmaceutical formulary assistant specializing in finding drug alternatives and analyzing formulary coverage.
Your role is to help users find alternative medications with the same active ingredients, compare costs, and understand formulary tiers.

Context from Formulary Documents:
{context}

User Question: {question}

Instructions:
1. Identify the requested drug and its active ingredient(s)
2. Identify the generic name for the provided question first
3. Find all alternative medications in the formulary with the same active ingredient(s)
4. Compare formulary tiers, generic name and associated costs/copays
5. Go through the medicine if there are generics available in the document provide those. Otherwise, if there are any medications used for the same or similar problem recommend those. Ensure you investigate all potential medications before suggesting anything as patient lives are on the line.
6. Highlight any prior authorization requirements or restrictions
7. Suggest the most cost-effective alternatives when appropriate
8. Include important details like:
   - Brand name and generic alternatives
   - Dosage forms and strengths available
   - Formulary tier (Tier 1, 2, 3, etc.)
   - Coverage restrictions (PA, ST, QL)
   - Estimated copay differences
8. Always remind users to consult their healthcare provider before making any changes to their medication regimen
9. Be specific about formulations and distinguish between different products
10. If no exact match is found, suggest checking the spelling or provide close matches

**NOTE:**
 For each drug you don't include, provide me with the reason of why it is not included.
Answer:
""")

    def _clean_drug_name_parentheses(self, name: str) -> str:
        """Clean drug name by removing parenthetical dosage form information.
        
        Examples:
        - "Relenza Diskhaler (Inhalation Aerosol Powder Breath Activated)" -> "Relenza Diskhaler"
        - "Ozempic (semaglutide)" -> "Ozempic (semaglutide)"  # Keep if it's generic name
        - "Advair HFA (fluticasone/salmeterol)" -> "Advair HFA (fluticasone/salmeterol)"  # Keep active ingredients
        """
        if not name or '(' not in name:
            return name
            
        # Define patterns for dosage forms that should be removed
        dosage_form_patterns = [
            r'\(.*(?:inhalation|aerosol|powder|tablet|capsule|injection|solution|cream|ointment|syrup|drops|oral|pen|prefilled|subcutaneous|topical|nasal|ophthalmic|otic|rectal|vaginal|intrauterine|intramuscular|intravenous|transdermal|sublingual|buccal|chewable|dispersible|extended|release|immediate|delayed|enteric|coated|film|activated|breath).*\)',
            r'\(.*(?:mg|mcg|ml|g|%).*\)',  # Dosage strength information
            r'\(.*(?:daily|weekly|monthly|twice|once|three times).*\)',  # Frequency information
        ]
        
        cleaned_name = name
        for pattern in dosage_form_patterns:
            # Remove dosage form parentheses but preserve the rest
            cleaned_name = re.sub(pattern, '', cleaned_name, flags=re.IGNORECASE).strip()
            
        # Clean up any double spaces that might result
        cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
        
        return cleaned_name if cleaned_name else name  # Return original if cleaning resulted in empty string

    def _extract_drug_name_and_form(self, full_drug_text: str) -> Dict[str, str]:
        """Extract drug name and medicine form from full drug text.
        
        Handles both cases:
        1. Parentheses format: "Oxycodone HCl (Oral Concentrate)"
        2. Direct format: "Metformin Tablet", "Lisinopril Oral Solution"
        
        Examples:
        - "Oxycodone HCl (Oral Concentrate)" -> {"drug_name": "Oxycodone HCl", "medicine_form": "Oral Concentrate"}
        - "Metformin Tablet" -> {"drug_name": "Metformin", "medicine_form": "Tablet"}
        - "Lisinopril Oral Solution" -> {"drug_name": "Lisinopril", "medicine_form": "Oral Solution"}
        - "Tramadol HCl (50MG Oral Tablet Immediate Release)" -> {"drug_name": "Tramadol HCl", "medicine_form": "50MG Oral Tablet Immediate Release"}
        """
        result = {"drug_name": full_drug_text.strip(), "medicine_form": ""}
        
        # Method 1: Look for parentheses that contain form information
        parentheses_match = re.search(r'^([^(]+?)\s*\(([^)]+)\)', full_drug_text.strip())
        
        if parentheses_match:
            potential_drug_name = parentheses_match.group(1).strip()
            potential_form = parentheses_match.group(2).strip()
            
            # Check if the content in parentheses looks like a medicine form
            form_indicators = [
                'oral', 'tablet', 'capsule', 'injection', 'solution', 'cream', 'ointment', 
                'syrup', 'drops', 'pen', 'prefilled', 'subcutaneous', 'topical', 'nasal',
                'ophthalmic', 'otic', 'rectal', 'vaginal', 'intrauterine', 'intramuscular',
                'intravenous', 'transdermal', 'sublingual', 'buccal', 'chewable', 
                'dispersible', 'extended', 'release', 'immediate', 'delayed', 'enteric',
                'coated', 'film', 'activated', 'breath', 'inhalation', 'aerosol', 'powder',
                'concentrate', 'external', 'patch', 'viscous', 'mouth', 'throat'
            ]
            
            # Also check for dosage patterns (mg, mcg, %, etc.)
            dosage_pattern = re.search(r'\d+(?:\.\d+)?\s*(mg|mcg|ml|g|%)', potential_form, re.IGNORECASE)
            
            if (any(indicator in potential_form.lower() for indicator in form_indicators) or 
                dosage_pattern or
                re.search(r'\d+(?:\.\d+)?-\d+(?:\.\d+)?', potential_form)):  # Range like "10-325MG"
                
                result["drug_name"] = potential_drug_name
                result["medicine_form"] = potential_form
                return result
        
        # Method 2: Look for medicine forms directly in the drug name (without parentheses)
        # Use comprehensive medicine forms list if available
        medicine_forms = []
        if hasattr(self, 'comprehensive_forms_list') and self.comprehensive_forms_list:
            medicine_forms = self.comprehensive_forms_list
        else:
            # Fallback to basic forms
            medicine_forms = [
                'tablet', 'tablets', 'capsule', 'capsules', 'injection', 'injections',
                'solution', 'solutions', 'cream', 'creams', 'ointment', 'ointments',
                'syrup', 'syrups', 'drops', 'gel', 'gels', 'spray', 'sprays',
                'patch', 'patches', 'powder', 'powders', 'liquid', 'liquids',
                'oral tablet', 'oral capsule', 'oral solution', 'oral concentrate',
                'topical cream', 'topical ointment', 'topical gel', 'topical solution',
                'external cream', 'external ointment', 'external patch',
                'subcutaneous injection', 'intramuscular injection', 'intravenous injection',
                'nasal spray', 'eye drops', 'ear drops', 'immediate release', 'extended release',
                'prefilled syringe', 'pen injector', 'chewable tablet', 'dissolving tablet'
            ]
        
        # Sort by length (longest first) to match longer forms first
        sorted_forms = sorted(medicine_forms, key=len, reverse=True)
        
        full_text_lower = full_drug_text.lower().strip()
        
        for form in sorted_forms:
            form_lower = form.lower()
            
            # Check if form appears at the end of the drug name
            if full_text_lower.endswith(' ' + form_lower) or full_text_lower.endswith(form_lower):
                # Extract drug name by removing the form
                if full_text_lower.endswith(' ' + form_lower):
                    drug_name_part = full_drug_text[:-len(' ' + form_lower)].strip()
                else:
                    drug_name_part = full_drug_text[:-len(form_lower)].strip()
                
                # Ensure we don't remove too much (drug name should be at least 2 characters)
                if len(drug_name_part) >= 2:
                    result["drug_name"] = drug_name_part
                    result["medicine_form"] = form.title()
                    return result
            
            # Check if form appears anywhere in the middle with word boundaries
            pattern = r'\b' + re.escape(form_lower) + r'\b'
            match = re.search(pattern, full_text_lower)
            if match:
                # Split the text at the form location
                start_pos = match.start()
                end_pos = match.end()
                
                before_form = full_drug_text[:start_pos].strip()
                form_found = full_drug_text[start_pos:end_pos].strip()
                after_form = full_drug_text[end_pos:].strip()
                
                # If there's content before the form, use it as drug name
                if len(before_form) >= 2:
                    result["drug_name"] = before_form
                    # Include any additional descriptors after the form
                    if after_form:
                        result["medicine_form"] = f"{form_found} {after_form}".strip()
                    else:
                        result["medicine_form"] = form_found
                    return result
        
        # If no form detected, return original text as drug name
        return result

    def _normalize_drug_name_for_comparison(self, drug_name: str) -> str:
        """
        Normalize drug name for comparison by removing salt forms like HCl, HBr, etc.
        This helps identify that 'Metformin' and 'Metformin HCl' are the same drug.
        
        Examples:
        - "Metformin HCl" -> "metformin"
        - "Tramadol HCl" -> "tramadol" 
        - "Diphenhydramine HBr" -> "diphenhydramine"
        - "Sertraline" -> "sertraline" (unchanged)
        """
        if not drug_name:
            return ""
        
        # Clean the name first
        cleaned_name = self._clean_drug_name_parentheses(drug_name.strip())
        
        # Common salt forms to remove (case-insensitive)
        salt_forms = [
            r'\s+hcl\b',           # Hydrochloride
            r'\s+hbr\b',           # Hydrobromide  
            r'\s+hydrochloride\b', # Full form
            r'\s+hydrobromide\b',  # Full form
            r'\s+sulfate\b',       # Sulfate
            r'\s+tartrate\b',      # Tartrate
            r'\s+maleate\b',       # Maleate
            r'\s+succinate\b',     # Succinate
            r'\s+fumarate\b',      # Fumarate
            r'\s+citrate\b',       # Citrate
            r'\s+phosphate\b',     # Phosphate
            r'\s+sodium\b',        # Sodium salt
            r'\s+potassium\b',     # Potassium salt
            r'\s+calcium\b',       # Calcium salt
            r'\s+magnesium\b',     # Magnesium salt
        ]
        
        normalized = cleaned_name.lower()
        
        # Remove salt forms
        for salt_pattern in salt_forms:
            normalized = re.sub(salt_pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up any extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized

    def _validate_medicine_with_pydantic(self, medicine_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate and clean medicine data using Pydantic models.
        Returns None if validation fails completely.
        """
        if not PYDANTIC_AVAILABLE:
            # Fallback to legacy cleaning
            return self._clean_medicine_data(medicine_data)
        
        try:
            # Create MedicineEntry with Pydantic validation
            validated_medicine = MedicineEntry(**medicine_data)
            
            # Convert back to dict with all the cleaned/validated data
            result = validated_medicine.dict()
            
            # Ensure all required fields are present and valid
            if (result.get('drug_name') and 
                result.get('generic_name') and 
                result.get('medicine_form') and 
                result.get('active_ingredient')):
                
                # print(f"Pydantic validation success: {result['drug_name']} ({result['medicine_form']})")
                return result
            else:
                # print(f"Pydantic validation failed: missing required fields")
                return None
                
        except Exception as e:
            # print(f"Pydantic validation error: {e}")
            
            # Try to salvage data with enhanced fallback
            try:
                # Extract what we can and apply intelligent defaults
                salvaged_data = {
                    'drug_name': medicine_data.get('drug_name', '').strip() or 'Unknown Medicine',
                    'generic_name': medicine_data.get('generic_name', '').strip() or medicine_data.get('drug_name', '').strip() or 'unknown',
                    'medicine_form': medicine_data.get('medicine_form', '').strip() or 'Tablet',
                    'active_ingredient': medicine_data.get('active_ingredient', '').strip() or medicine_data.get('generic_name', '').strip() or 'unknown',
                    'therapeutic_class': medicine_data.get('therapeutic_class', '').strip() or 'Unknown',
                    'tier': medicine_data.get('tier', '').strip() or 'Unknown',
                    'restrictions': medicine_data.get('restrictions', '').strip() or 'None',
                    'strength': medicine_data.get('strength', '').strip() or '',
                    'source_document': medicine_data.get('source_document', ''),
                    'confidence': 0.5  # Lower confidence for salvaged data
                }
                
                # Validate salvaged data doesn't have problematic values
                for field in ['drug_name', 'generic_name']:
                    if salvaged_data[field].lower() in ['none', 'unknown', 'same', 'unclear', '']:
                        return None  # Can't salvage
                
                # print(f"Salvaged medicine data: {salvaged_data['drug_name']}")
                return salvaged_data
                
            except Exception as salvage_error:
                # print(f"Failed to salvage medicine data: {salvage_error}")
                return None

    def _extract_medicines_with_structured_llm(self, text: str, source_file: str) -> List[Dict[str, Any]]:
        """
        🎯 ENHANCED: LLM extraction with structured outputs, chunking, workers, and 80s timeout.
        
        Now uses Pydantic models as response format to force LLM compliance.
        Includes chunking, parallel processing, retry logic, and comprehensive error handling.
        Ensures NO chunks are lost due to timeouts and NO "None" values in output.
        """
        if not PYDANTIC_AVAILABLE or not text.strip():
            # print("Structured outputs not available, falling back to legacy extraction")
            return self._extract_medicines_legacy_method(text, source_file)
        
        # print(f"Using enhanced structured LLM extraction with workers for {Path(source_file).name}...")
        
        # Use smaller chunks to reduce timeout risk
        text_chunks = [text[i:i+self.chunk_size_for_extraction] for i in range(0, len(text), self.chunk_size_for_extraction)]
        # print(f"Processing {len(text_chunks)} chunks (max {self.chunk_size_for_extraction} chars each) with structured outputs...")
        
        all_validated_medicines = []
        failed_chunks = []  # Track failed chunks for retry
        
        # Create extraction prompt that FORCES the LLM to use our schema
        extraction_prompt = ChatPromptTemplate.from_template("""
You are a pharmaceutical data extraction expert. Extract ALL medicines from the provided formulary text and return the results in JSON format.

**CRITICAL INSTRUCTIONS:**
1. You MUST return valid JSON matching the exact schema provided
2. NEVER use "None", "unknown", "same", or "unclear" values
3. For missing generic_name: extract/infer from drug_name or use drug_name.lower()
4. For missing medicine_form: analyze drug_name or use "Tablet" as default
5. For missing strength: use unknown
6. For missing tier: use "Unknown" instead of None
7. For missing restrictions: use "None" instead of empty
8. Return your response as a properly formatted JSON object

**MEDICINE FORM OPTIONS (pick exact match):**
Tablet, Capsule, Injection, Intravenous, Oral, Topical, Cream, Ointment, Solution, 
Suspension, Syrup, Drops, Spray, Patch, Gel, Inhaler, Suppository, Lotion, Powder, 
Oral Concentrate, Oral Solution, External Cream, External Ointment, Nasal Spray, 
Eye Drops, Ear Drops, Sublingual, Buccal, Rectal, Vaginal

**EXAMPLE JSON OUTPUT FORMAT:**
{{
  "medicines": [
    {{
      "drug_name": "Metformin HCl",
      "generic_name": "metformin", 
      "medicine_form": "Tablet",
      "active_ingredient": "metformin",
      "therapeutic_class": "Antidiabetic",
      "tier": "Tier 1",
      "restrictions": "None",
      "strength": "500mg"
    }}
  ],
  "extraction_metadata": {{
    "total_found": 1,
    "extraction_method": "llm_structured_output",
    "confidence": 0.9
  }}
}}

**TEXT TO EXTRACT FROM:**
{text}

**RESPONSE (JSON format only):**
""")
        
        def process_chunk_with_retry(chunk_data, retry_count=0):
            """Process a single chunk with structured outputs and exponential backoff retry."""
            chunk_idx, chunk = chunk_data
            thread_id = threading.current_thread().ident
            
            # Exponential backoff delay for retries
            if retry_count > 0:
                import time
                delay = min(2 ** retry_count, 10)  # Max 10 second delay
                # print(f"  Retry {retry_count} for Chunk {chunk_idx + 1} after {delay}s delay...")
                time.sleep(delay)
            
            # print(f"  Chunk {chunk_idx + 1}/{len(text_chunks)} [Thread {thread_id}] (Attempt {retry_count + 1})...")
            
            try:
                # DOCKER-COMPATIBLE: Try multiple approaches for structured extraction
                chunk_medicines = []
                
                # Method 1: Try modern structured output if available
                if self.structured_llm and hasattr(self.structured_llm, 'with_structured_output'):
                    try:
                        prompt_text = extraction_prompt.format(text=chunk)
                        validated_response = self.structured_llm.invoke(prompt_text)
                        
                        if hasattr(validated_response, 'medicines'):
                            chunk_medicines = [medicine.model_dump() for medicine in validated_response.medicines]
                        else:
                            raise ValueError("No medicines attribute in response")
                            
                    except Exception as modern_error:
                        # print(f"Modern structured output failed: {modern_error}")
                        chunk_medicines = []
                
                # Method 2: Try JSON mode structured output if Method 1 failed
                if not chunk_medicines and self.structured_llm:
                    try:
                        # Use direct invocation with HumanMessage for compatibility
                        from langchain_core.messages import HumanMessage
                        prompt_text = extraction_prompt.format(text=chunk)
                        messages = [HumanMessage(content=prompt_text)]
                        
                        response = self.structured_llm.invoke(messages)
                        
                        # Handle different response types
                        response_text = ""
                        if hasattr(response, 'content'):
                            response_text = response.content
                        elif hasattr(response, 'choices') and len(response.choices) > 0:
                            # Handle LegacyAPIResponse format 
                            response_text = response.choices[0].message.content
                        elif isinstance(response, str):
                            response_text = response
                        else:
                            response_text = str(response)
                        
                        # Parse JSON response
                        import json
                        try:
                            response_data = json.loads(response_text)
                        except json.JSONDecodeError:
                            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                            if json_match:
                                response_data = json.loads(json_match.group())
                            else:
                                raise ValueError("No valid JSON found")
                        
                        validated_response = MedicineExtractionResponse(**response_data)
                        chunk_medicines = [medicine.model_dump() for medicine in validated_response.medicines]
                        
                    except Exception as json_error:
                        # print(f"JSON mode structured output failed: {json_error}")
                        chunk_medicines = []
                
                # Method 3: Fallback to standard chain extraction
                if not chunk_medicines:
                    try:
                        extraction_chain = extraction_prompt | self.llm | StrOutputParser()
                        response_text = extraction_chain.invoke({"text": chunk})
                        
                        import json
                        try:
                            response_data = json.loads(response_text)
                        except json.JSONDecodeError:
                            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                            if json_match:
                                response_data = json.loads(json_match.group())
                            else:
                                raise ValueError("No valid JSON found in chain response")
                        
                        validated_response = MedicineExtractionResponse(**response_data)
                        chunk_medicines = [medicine.model_dump() for medicine in validated_response.medicines]
                        
                    except Exception as chain_error:
                        # print(f"All extraction methods failed: {chain_error}")
                        raise chain_error
                
                # CRITICAL: Apply drug name/form cleaning to structured extraction results
                cleaned_medicines = []
                for medicine in chunk_medicines:
                    # Apply comprehensive medicine data cleaning including LLM drug name filtering
                    cleaned_medicine = self._clean_medicine_data(medicine)
                    
                    # Additional validation: ensure it's actually a medicine
                    if self._is_valid_medicine_entry(cleaned_medicine):
                        #TODO
                        # cleaned_medicines.append(cleaned_medicine)
                        final_name = self._finalize_clean_drug_name(cleaned_medicine.get('drug_name'))
                        if final_name:
                            cleaned_medicine['drug_name'] = final_name
                            cleaned_medicines.append(cleaned_medicine)
                        else:
                            print(f"Skipping invalid drug name: {cleaned_medicine.get('drug_name')}")
                # Add source metadata to cleaned medicines
                for medicine in cleaned_medicines:
                    medicine['source_document'] = Path(source_file).name
                    medicine['extraction_method'] = 'structured_llm'
                    medicine['chunk_index'] = chunk_idx
                
                if cleaned_medicines:
                    # print(f"  Chunk {chunk_idx + 1}: extracted {len(cleaned_medicines)} medicines with structured outputs and LLM-cleaned names")
                    return cleaned_medicines
                else:
                    # print(f"  Chunk {chunk_idx + 1}: no valid medicines found after cleaning")
                    return []
                    
            except Exception as e:
                error_str = str(e).lower()
                if "timeout" in error_str or "timed out" in error_str:
                    # print(f"    Chunk {chunk_idx + 1}: Timeout on attempt {retry_count + 1}")
                    pass
                else:
                    # print(f"    ❌ Chunk {chunk_idx + 1}: Error on attempt {retry_count + 1} - {str(e)}")
                    pass
                
                # Retry if under limit
                if retry_count < self.max_chunk_retries:
                    return process_chunk_with_retry(chunk_data, retry_count + 1)
                else:
                    # print(f"    Chunk {chunk_idx + 1}: Max retries exceeded, adding to failed chunks")
                    failed_chunks.append(chunk_data)
                    return []
        
        # Process chunks with reduced parallelism to avoid rate limits
        max_workers = min(self.max_extraction_workers, len(text_chunks))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunk processing jobs with structured outputs
            future_to_chunk = {
                executor.submit(process_chunk_with_retry, (idx, chunk)): (idx, chunk)
                for idx, chunk in enumerate(text_chunks)
            }
            
            # Collect results as they complete with 80s timeout
            for future in as_completed(future_to_chunk):
                chunk_idx, original_chunk = future_to_chunk[future]
                try:
                    chunk_medicines = future.result(timeout=80)  # 80 second timeout
                    if chunk_medicines:
                        all_validated_medicines.extend(chunk_medicines)
                    else:
                        failed_chunks.append((chunk_idx, original_chunk))
                except Exception as exc:
                    print(f"    💥 Chunk {chunk_idx + 1} generated an exception: {exc}")
                    failed_chunks.append((chunk_idx, original_chunk))
        
        # RECOVERY: Process failed chunks with pattern extraction
        if failed_chunks:
            # print(f"RECOVERY: Processing {len(failed_chunks)} failed chunks with pattern extraction...")
            for chunk_idx, failed_chunk in failed_chunks:
                # print(f"  Recovering Chunk {chunk_idx + 1} with pattern extraction...")
                try:
                    pattern_results = self._parse_text_with_patterns(failed_chunk, source_file)
                    for result in pattern_results:
                        result['extraction_method'] = 'pattern_fallback_after_structured_timeout'
                        result['chunk_index'] = chunk_idx
                    all_validated_medicines.extend(pattern_results)
                    # print(f"    Recovered {len(pattern_results)} medicines from failed Chunk {chunk_idx + 1}")
                except Exception as recovery_error:
                    # print(f"    Pattern recovery failed for Chunk {chunk_idx + 1}: {str(recovery_error)}")
                    pass
        
        success_rate = (len(text_chunks) - len(failed_chunks)) / len(text_chunks) * 100
        # print(f"Structured extraction complete: {len(all_validated_medicines)} medicines with guaranteed data quality")
        # print(f"📊 Success rate: {success_rate:.1f}% ({len(text_chunks) - len(failed_chunks)}/{len(text_chunks)} chunks successful)")
        
        return all_validated_medicines
    
    def _extract_medicines_legacy_method(self, text: str, source_file: str) -> List[Dict[str, Any]]:
        """Legacy extraction method for fallback."""
        return self._parse_text_with_patterns(text, source_file)

    def _extract_drug_name_and_form_from_raw(self, raw_drug_name: str) -> Dict[str, str]:
        """
        Extract clean drug name and medicine form from a raw drug name string.
        Handles cases like 'methylprednisolone sodium succ intravenous' -> 
        drug_name='methylprednisolone sodium succ', medicine_form='intravenous'
        """
        if not raw_drug_name or not raw_drug_name.strip():
            return {'drug_name': '', 'medicine_form': ''}
        
        raw_name = raw_drug_name.strip().lower()
        
        # Get comprehensive list of medicine forms from our master list
        medicine_forms = []
        if hasattr(self, 'medicine_forms_master'):
            try:
                medicine_forms = MedicineFormsMaster.get_all_forms()
            except:
                pass
        
        # Fallback common forms if master list not available
        if not medicine_forms:
            medicine_forms = [
                # Basic forms
                'tablet', 'capsule', 'injection', 'solution', 'cream', 'ointment',
                'gel', 'patch', 'suppository', 'drops', 'spray', 'inhaler',
                'syrup', 'suspension', 'powder', 'granules', 'lotion','shampoo',
                
                # Route-specific forms
                'intravenous', 'intramuscular', 'subcutaneous', 'oral', 'topical',
                'sublingual', 'buccal', 'nasal', 'ophthalmic', 'otic', 'rectal',
                'vaginal', 'transdermal', 'inhaled', 'nebulizer', 'aerosol',
                
                # Extended forms with routes
                'oral tablet', 'oral capsule', 'oral solution', 'oral suspension',
                'topical cream', 'topical ointment', 'topical gel', 'topical solution',
                'topical lotion', 'topical patch', 'topical spray',
                'nasal spray', 'nasal drops', 'eye drops', 'ear drops',
                'oral concentrate', 'oral syrup', 'oral powder',
                
                # Special formulations
                'microspheres', 'microspheres gel', 'microsphere', 'topical microspheres',
                'tretinoin microspheres', 'microspheres topical gel',
                'extended-release', 'immediate-release', 'controlled-release',
                'sustained-release', 'delayed-release', 'enteric-coated',
                'chewable', 'orally-disintegrating', 'effervescent',
                'film-coated', 'sugar-coated', 'hard-gelatin', 'soft-gelatin',
                'liposomal', 'nanoparticle', 'emulsion',
                
                # Complex formulations with additives
                'with ethanol topical gel', 'with ethanol topical solution',
                'with ethanol gel', 'with ethanol solution', 'with ethanol cream',
                'ethanol topical gel', 'ethanol topical solution', 'ethanol gel',
                'topical gel with ethanol', 'topical solution with ethanol',
                'with benzyl alcohol', 'benzyl alcohol gel', 'benzyl alcohol solution',
                
                # Abbreviations
                'tab', 'tabs', 'cap', 'caps', 'inj', 'sol', 'susp', 'cr', 'oint',
                'iv', 'im', 'po', 'top', 'xl', 'er', 'sr', 'la', 'cd', 'od', 'xr'
            ]
        
        # Convert to lowercase for matching
        forms_lower = [form.lower() for form in medicine_forms]
        
        # Sort forms by length (longest first) to match more specific forms first
        forms_lower_sorted = sorted(forms_lower, key=len, reverse=True)
        
        # Split the raw name into words
        words = raw_name.split()
        
        # Find forms in the name (checking longest matches first)
        found_forms = []
        remaining_words = words.copy()
        
        # Check for multi-word forms first, starting with longest possible matches
        for form in forms_lower_sorted:
            form_words = form.split()
            if len(form_words) > 1:  # Multi-word forms
                # Look for this form in the text
                for i in range(len(words) - len(form_words) + 1):
                    potential_match = ' '.join(words[i:i + len(form_words)])
                    if potential_match == form:
                        found_forms.append(form)
                        # Mark these words as used
                        for j in range(i, i + len(form_words)):
                            if j < len(remaining_words):
                                remaining_words[j] = None
                        break
        
        # Check for single word forms (only if not already matched)
        for form in forms_lower_sorted:
            form_words = form.split()
            if len(form_words) == 1:  # Single word forms
                for i, word in enumerate(words):
                    if word == form and remaining_words[i] is not None:
                        found_forms.append(form)
                        remaining_words[i] = None
                        break
        
        # Clean up remaining words to get drug name
        clean_words = [word for word in remaining_words if word is not None]
        clean_drug_name = ' '.join(clean_words).strip()
        
        # Determine the primary medicine form
        primary_form = ''
        if found_forms:
            # Standardize and pick the most specific form
            standardized_forms = []
            for form in found_forms:
                if hasattr(self, 'medicine_forms_master'):
                    try:
                        std_form = MedicineFormsMaster.find_best_match(form)
                        if std_form:
                            standardized_forms.append(std_form)
                    except:
                        standardized_forms.append(form.title())
                else:
                    # Enhanced standardization for better form mapping
                    form_mapping = {
                        'tab': 'Tablet', 'tabs': 'Tablet', 'tablet': 'Tablet',
                        'cap': 'Capsule', 'caps': 'Capsule', 'capsule': 'Capsule',
                        'inj': 'Injection', 'injection': 'Injection',
                        'sol': 'Solution', 'solution': 'Solution',
                        'susp': 'Suspension', 'suspension': 'Suspension',
                        'cr': 'Cream', 'cream': 'Cream',
                        'oint': 'Ointment', 'ointment': 'Ointment',
                        'gel': 'Gel', 'topical gel': 'Gel',
                        'iv': 'Intravenous', 'intravenous': 'Intravenous',
                        'im': 'Intramuscular', 'intramuscular': 'Intramuscular',
                        'po': 'Oral', 'oral': 'Oral',
                        'top': 'Topical', 'topical': 'Topical',
                        'xl': 'Extended-Release', 'er': 'Extended-Release', 'extended-release': 'Extended-Release',
                        'sr': 'Sustained-Release', 'sustained-release': 'Sustained-Release',
                        'la': 'Long-Acting', 'cd': 'Controlled-Release', 'controlled-release': 'Controlled-Release',
                        'od': 'Once-Daily', 'xr': 'Extended-Release',
                        
                        # Specific mappings for complex forms
                        'oral capsule': 'Capsule', 'oral tablet': 'Tablet',
                        'topical cream': 'Cream', 'topical ointment': 'Ointment',
                        'topical gel': 'Gel', 'topical solution': 'Solution',
                        'microspheres': 'Gel', 'microspheres gel': 'Gel',
                        'microspheres topical gel': 'Gel', 'topical microspheres': 'Gel',
                        'tretinoin microspheres': 'Gel',
                        'nasal spray': 'Nasal Spray', 'eye drops': 'Eye Drops', 'ear drops': 'Ear Drops',
                        
                        # Handle complex formulations (like "with ethanol")
                        'with ethanol topical gel': 'Gel', 'with ethanol topical solution': 'Solution',
                        'with ethanol gel': 'Gel', 'with ethanol solution': 'Solution',
                        'ethanol topical gel': 'Gel', 'ethanol topical solution': 'Solution',
                        'topical gel with ethanol': 'Gel', 'topical solution with ethanol': 'Solution'
                    }
                    standardized_forms.append(form_mapping.get(form, form.title()))
            
            # Pick the most specific/longest form as primary
            primary_form = max(standardized_forms, key=len) if standardized_forms else ''
        
        # If no drug name remains after form extraction, use original
        if not clean_drug_name:
            clean_drug_name = raw_drug_name
            primary_form = ''
        
        return {
            'drug_name': clean_drug_name.title(),
            'medicine_form': primary_form if primary_form else 'None'
        }

    def _clean_medicine_data(self, medicine: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean medicine data to fix common LLM extraction issues:
        - Replace "same", "unknown", "unclear" with proper values
        - Separate drug names from medicine forms properly
        - Ensure generic names are different from drug names where appropriate
        - Set medicine_form to "None" instead of "unknown"
        - Clean up strength and tier formatting
        """
        cleaned_medicine = medicine.copy()
        raw_drug_name = cleaned_medicine.get('drug_name', '').strip()
        
        # STEP 1: Clean and separate drug name from medicine form using number-based splitting
        if raw_drug_name:
            # Extract just the drug name up to the first number (consistent with search behavior)
            base_drug_name = re.split(r'\s*\d', raw_drug_name)[0].strip() if raw_drug_name else raw_drug_name
            
            # Then use extraction function to get form information from original name
            name_and_form = self._extract_drug_name_and_form_from_raw(raw_drug_name)
            extracted_form = name_and_form['medicine_form']
            
            # Use the base drug name as the final drug name
            cleaned_medicine['drug_name'] = base_drug_name
            
            # If we extracted a form from the drug name, use it (unless already specified)
            current_form = cleaned_medicine.get('medicine_form', '').strip()
            if not current_form or current_form.lower() in ['same', 'unknown', 'unclear', 'not specified']:
                cleaned_medicine['medicine_form'] = extracted_form if extracted_form and extracted_form.lower() not in ['none', 'unknown'] else 'Unknown'  # Use 'Unknown' instead of 'Tablet' as default
        else:
            cleaned_drug_name = raw_drug_name
        
        # Get the cleaned drug name for further processing
        cleaned_drug_name = cleaned_medicine.get('drug_name', raw_drug_name)
        
        # STEP 2: Clean generic_name
        generic_name = cleaned_medicine.get('generic_name', '').strip().lower()
        if generic_name in ['same', 'unknown', 'unclear', 'not specified', '']:
            # Try to extract a proper generic name from clean drug name
            drug_name_lower = cleaned_drug_name.lower()
            # Remove brand indicators and common suffixes to get likely generic
            generic_candidate = re.sub(r'\b(brand|®|™|cr|xl|er|sr|la|cd|od|xr)\b', '', drug_name_lower, flags=re.IGNORECASE)
            generic_candidate = re.sub(r'\s+', ' ', generic_candidate).strip()
            cleaned_medicine['generic_name'] = generic_candidate if generic_candidate else cleaned_drug_name.lower()
        else:
            cleaned_medicine['generic_name'] = generic_name
        
        # STEP 3: Clean and standardize medicine_form using our comprehensive forms list
        medicine_form = cleaned_medicine.get('medicine_form', '').strip().lower()
        if medicine_form in ['same', 'unknown', 'unclear', 'not specified', '']:
            # Try to extract medicine form from the drug name if not provided
            if raw_drug_name:
                extracted_info = self._extract_drug_name_and_form_from_raw(raw_drug_name)
                extracted_form = extracted_info.get('medicine_form', '')
                if extracted_form and extracted_form.lower() != 'none':
                    cleaned_medicine['medicine_form'] = extracted_form
                else:
                    # Try to find common forms in the drug name
                    common_forms = ['tablet', 'capsule', 'injection', 'cream', 'ointment', 'solution', 'syrup', 
                                   'drops', 'spray', 'patch', 'gel', 'intravenous', 'oral', 'topical', 'shampoo']
                    drug_name_lower = raw_drug_name.lower()
                    found_form = None
                    for form in common_forms:
                        if form in drug_name_lower:
                            found_form = form
                            break
                    cleaned_medicine['medicine_form'] = found_form.title() if found_form else medicine_form.title()  # Preserve original form if not found
            else:
                cleaned_medicine['medicine_form'] = medicine_form.title()  # Preserve original form
        elif medicine_form == 'none':
            # Even if LLM said "none", try to extract from drug name
            if raw_drug_name:
                extracted_info = self._extract_drug_name_and_form_from_raw(raw_drug_name)
                extracted_form = extracted_info.get('medicine_form', '')
                cleaned_medicine['medicine_form'] = extracted_form if extracted_form and extracted_form.lower() not in ['none', 'unknown'] else 'Unknown'
            else:
                cleaned_medicine['medicine_form'] = 'Unknown'  # Use 'Unknown' when no form can be determined
        else:
            # Use our comprehensive medicine forms to standardize
            if hasattr(self, 'medicine_forms_master'):
                standardized_form = MedicineFormsMaster.find_best_match(medicine_form)
                cleaned_medicine['medicine_form'] = standardized_form if standardized_form else medicine_form.title()
            else:
                # Fallback standardization
                form_mapping = {
                    'tab': 'tablet', 'tabs': 'tablet', 
                    'cap': 'capsule', 'caps': 'capsule',
                    'inj': 'injection', 'sol': 'solution',
                    'susp': 'suspension', 'cr': 'cream',
                    'oint': 'ointment', 'iv': 'intravenous',
                    'im': 'intramuscular', 'po': 'oral',
                    'top': 'topical',
                    'shampoo': 'shampoo'
                }
                cleaned_form = form_mapping.get(medicine_form, medicine_form)
                cleaned_medicine['medicine_form'] = cleaned_form.title()
        
        # Set dosage_form to match medicine_form for consistency
        cleaned_medicine['dosage_form'] = cleaned_medicine['medicine_form']
        
        # STEP 4: Clean strength
        strength = cleaned_medicine.get('strength', '').strip()
        if strength.lower() in ['same', 'unknown', 'unclear', 'not specified', '']:
            cleaned_medicine['strength'] = 'None'
        elif strength and not re.search(r'\d', strength):  # No numbers in strength
            cleaned_medicine['strength'] = 'None'
        
        # STEP 5: Clean tier
        tier = cleaned_medicine.get('tier', '').strip()
        if tier.lower() in ['same', 'unknown', 'unclear', 'not specified', '']:
            cleaned_medicine['tier'] = 'Unknown'
        
        # STEP 6: Clean restrictions
        restrictions = cleaned_medicine.get('restrictions', '').strip()
        if restrictions.lower() in ['same', 'unknown', 'unclear', 'not specified', '']:
            cleaned_medicine['restrictions'] = 'None'
        elif restrictions.lower() == 'none':
            cleaned_medicine['restrictions'] = 'None'  # Standardize
        
        # STEP 7: Set active_ingredient properly
        active_ingredient = cleaned_medicine.get('active_ingredient', '').strip().lower()
        if active_ingredient in ['same', 'unknown', 'unclear', 'not specified', '']:
            cleaned_medicine['active_ingredient'] = cleaned_medicine['generic_name'].lower()
        else:
            cleaned_medicine['active_ingredient'] = active_ingredient
        
        # STEP 8: Ensure confidence is set
        if not cleaned_medicine.get('confidence'):
            cleaned_medicine['confidence'] = 'medium'
        
        return cleaned_medicine

    def _is_valid_drug_name(self, name: str) -> bool:
        """Enhanced validation to filter out medicine forms, units, and other non-drug terms."""
        if not name or not name.strip():
            return False
            
        # First clean the name to remove dosage form parentheses
        cleaned_name = self._clean_drug_name_parentheses(name.strip())
        name_lower = cleaned_name.lower().strip()
        
        # Minimum length check
        if len(cleaned_name) < 2:
            return False
        
        # CRITICAL: Filter out obvious medicine forms and units that were incorrectly identified as drug names
        medicine_forms_and_units = {
            # Medicine forms
            'tablet', 'capsule', 'injection', 'intravenous', 'oral', 'topical', 'cream', 'ointment', 
            'solution', 'suspension', 'syrup', 'drops', 'spray', 'patch', 'gel', 'inhaler', 
            'suppository', 'lotion', 'shampoo', 'powder', 'concentrate', 'syringe', 'pen', 'prefilled',
            'nasal', 'ophthalmic', 'otic', 'rectal', 'vaginal', 'sublingual', 'buccal',
            'extended', 'immediate', 'delayed', 'release', 'coated', 'film', 'chewable',
            'dissolving', 'enteric', 'modified', 'controlled', 'sustained',
            
            # Units and measurements  
            'mg', 'mcg', 'ml', 'g', 'kg', 'mg/ml', 'mcg/ml', 'iu', 'units', 'unit',
            '%', 'percent', 'mmol', 'meq', 'ppm', 'dose', 'doses',
            
            # Restriction codes and administrative terms
            'pa', 'st', 'ql', 'prior authorization', 'step therapy', 'quantity limit',
            'pa, ql', 'st, ql', 'pa, st', 'pa, st, ql', 'ql (60/30)', 'ql (30/30)',
            
            # Formatting artifacts and common misidentifications
            'capitalized', 'lowercase', 'italic', 'bold', 'requirements', 'various',
            'unknown', 'none', 'not applicable', 'not specified', 'same', 'unclear',
            'tier1', 'tier2', 'tier3', 'tier4', 'tier5', 'tier 1', 'tier 2', 'tier 3',
            
            # Therapeutic categories and device types
            'therapy for acne', 'wearable', 'injector', 'release(dr/ec)', 'release (dr/ec)',
            'release(ec/dr)', 'release (ec/dr)', 'ulcer therapy',
            'immunology', 'biotechnology', 'miniquick', 'vaccines', 'immunologicals',
            'therapy', 'device', 'wearable device', 'injector pen', 'delivery device',
            'technology', 'system', 'platform', 'biosimilar', 'generic version',
            
            # Medical specialties and categories
            'dermatology', 'cardiology', 'endocrinology', 'gastroenterology', 
            'rheumatology', 'oncology', 'neurology', 'psychiatry', 'infectious disease',
            'pulmonology', 'nephrology', 'hematology', 'urology', 'ophthalmology',
            'otolaryngology', 'gynecology', 'pediatrics', 'geriatrics',
            
            # Therapeutic categories
            'anti-inflammatory', 'antibiotic', 'antiviral', 'antifungal', 'antihistamine',
            'analgesic', 'anesthetic', 'sedative', 'stimulant', 'antidepressant',
            'antipsychotic', 'anxiolytic', 'anticonvulsant', 'muscle relaxant',
            
            # Device and delivery terms
            'auto-injector', 'pen device', 'inhaler device', 'pump', 'monitor',
            'meter', 'lancet', 'strip', 'cartridge', 'refill', 'disposable',
            
            # Administrative and document terms
            'formulary', 'coverage', 'benefit', 'copay', 'deductible', 'prior auth',
            'generic', 'brand', 'preferred', 'non-preferred', 'excluded', 'covered',
            'authorization', 'approval', 'restriction', 'limit', 'quantity',
            
            # Common extraction errors
            'drug', 'medication', 'medicine', 'pharmaceutical', 'therapy', 'treatment',
            'active ingredient', 'therapeutic class', 'dosage form', 'strength',
            
            # Time-related terms
            'daily', 'weekly', 'monthly', 'yearly', 'morning', 'evening', 'night',
            'bedtime', 'twice daily', 'three times', 'four times', 'as needed',
            
            # Document structure terms
            'page', 'section', 'table', 'column', 'row', 'header', 'footer', 'title',
            'updated', 'effective', 'version', 'revision', 'date'
        }
        
        # Check against the comprehensive exclusion list
        if name_lower in medicine_forms_and_units:
            return False
        
        # Check for dosage/strength only patterns
        dosage_only_patterns = [
            r'^\d+\s*(mg|mcg|ml|g|%|units?|iu)$',  # Just numbers with units
            r'^(various|unknown|not?\s*applicable|not?\s*specified|same|unclear)$',
            r'^(pa|st|ql)(\s*,\s*(pa|st|ql))*$',  # Just restriction codes
            r'^ql\s*\(\d+/\d+\)$',  # Quantity limit format like "ql (60/30)"
            r'^tier\s*\d+?$',  # Just tier numbers
            r'^\d+(\.\d+)?\s*(mg|mcg|ml|g|%)(\s*/\s*\d+(\.\d+)?\s*(mg|mcg|ml|g|%))*$'  # Complex dosage
        ]
        
        for pattern in dosage_only_patterns:
            if re.match(pattern, name_lower):
                return False
        
        # Check if it contains only non-letter characters
        if not re.search(r'[a-zA-Z]', name_lower):
            return False
        
        # Reject if it's just a single word that matches common forms
        words = name_lower.split()
        if len(words) == 1 and words[0] in medicine_forms_and_units:
            return False
        
        # Additional pattern checks for problematic entries
        problematic_patterns = [
            r'^(capitalized|lowercase|italic|bold|requirements)$',  # Formatting terms
            r'^(syringe|mg|pa)$',  # Single word units/codes
            r'^\w+\s+(italic|bold|capitalized|lowercase)$',  # Word + formatting
            r'^ql\s*\([^)]+\)$',  # Any QL pattern with parentheses
            r'^release\s*\([^)]*dr[^)]*ec[^)]*\)$',  # Release (Dr/Ec) variations
            r'^release\s*\([^)]*ec[^)]*dr[^)]*\)$',  # Release (Ec/Dr) variations
        ]
        
        for pattern in problematic_patterns:
            if re.match(pattern, name_lower):
                return False
        
        # Length checks
        if len(name_lower) > 50:  # Unreasonably long
            return False
            
        if name_lower.count(' ') > 4:  # Too many spaces
            return False
        
        # Final check: if it's a very short name, be extra cautious
        if len(name_lower) <= 3:
            # Allow only if it's likely a real drug abbreviation or short name
            if name_lower in {'iv', 'hc', 'asa', 'otc', 'rx'}:  # Common medical abbreviations
                return False
            # Allow 2-3 letter combinations that could be real drugs (like "iv" -> but reject it)
            # This is conservative but prevents most false positives
            
        return True

    def _get_input_suggestions(self, invalid_input: str) -> List[str]:
        """Get helpful suggestions when user enters an invalid drug name."""
        suggestions = []
        
        # If they entered a common non-drug term, provide examples
        invalid_lower = invalid_input.lower().strip()
        
        if invalid_lower in ['tablet', 'capsule', 'pill', 'medication', 'drug', 'medicine']:
            suggestions = [
                "Try entering a specific drug name like 'Ozempic', 'Lisinopril', or 'Metformin'",
                "Enter brand names (e.g., Lipitor, Crestor) or generic names (e.g., atorvastatin, rosuvastatin)"
            ]
        elif invalid_lower in ['mg', 'mcg', 'ml', 'dose', 'dosage']:
            suggestions = [
                "Enter just the drug name without dosage (e.g., 'Metformin' instead of 'Metformin 500mg')",
                "Try searching for: Ozempic, Wegovy, Zepbound, Trulicity"
            ]
        elif any(month in invalid_lower for month in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']):
            suggestions = [
                "It looks like you entered a date. Please enter a medication name instead.",
                "Examples of drug names: Ozempic, Lisinopril, Atorvastatin, Metformin"
            ]
        elif len(invalid_lower) < 2:  # Reduced from 3 to 2
            suggestions = [
                "Please enter at least 2 characters for a drug name.",
                "Common drugs to try: Ozempic, Wegovy, Lipitor, Crestor, Nexium"
            ]
        else:
            # Try to find similar sounding drugs in our database
            if hasattr(self, 'all_drug_names') and self.all_drug_names:
                import difflib
                close_matches = difflib.get_close_matches(invalid_input, self.all_drug_names, n=3, cutoff=0.6)
                if close_matches:
                    suggestions = [f"Did you mean: {', '.join(close_matches)}?"]
                else:
                    suggestions = [
                        "Please check the spelling and try again.",
                        "Popular drugs to search: Ozempic, Wegovy, Zepbound, Lisinopril, Metformin"
                    ]
            else:
                suggestions = [
                    "Please enter a valid medication name.",
                    "Examples: Ozempic, Lisinopril, Atorvastatin, Metformin, Nexium"
                ]
        
        return suggestions

    def _filter_non_medicines_with_llm(self, alternatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use the LLM to classify each item by name and drop non-medicines.
        
        Ultra-optimized version that processes each drug name individually in parallel 
        for maximum speed and lowest latency.
        """
        if not alternatives:
            return alternatives

        # Collect names to classify
        drug_names = [alt.get('drug_name', '').strip() for alt in alternatives if alt.get('drug_name')]
        if not drug_names:
            return alternatives

        # print(f"Starting parallel LLM classification for {len(drug_names)} drug names...")
        start_time = datetime.now()

        def _classify_single_name(name_and_index):
            """Classify a single drug name with LLM - optimized for parallel execution."""
            name, original_index = name_and_index
            
            # Use a streamlined prompt for single-name classification
            prompt = f"""Is "{name}" a specific medicine (brand or generic drug name)?

Respond with ONLY this JSON format:
{{"is_medicine": true/false, "classification": "medicine/drug_class/dosage_form/other", "reason": "brief reason"}}

Examples:
- "Metformin" -> {{"is_medicine": true, "classification": "medicine", "reason": "diabetes medication"}}
- "Antigout Agents" -> {{"is_medicine": false, "classification": "drug_class", "reason": "therapeutic category"}}
- "Oral Tablet" -> {{"is_medicine": false, "classification": "dosage_form", "reason": "dosage form"}}

For "{name}":"""

            try:
                # # 🔍 CONSOLE LOG: Log each individual classification request
                # print(f"\n🤖 OPENAI CLASSIFICATION REQUEST #{original_index + 1} for '{name}':")
                # print(f"📝 Prompt sent to OpenAI:")
                # print(f"{'-'*60}")
                # print(prompt)
                # print(f"{'-'*60}")
                
                response = self.llm.invoke(prompt)
                if hasattr(response, 'content'):
                    response_text = response.content.strip()
                elif hasattr(response, 'choices') and len(response.choices) > 0:
                    # Handle LegacyAPIResponse format
                    response_text = response.choices[0].message.content.strip()
                else:
                    response_text = str(response).strip()
                
                # # 🔍 CONSOLE LOG: Log each individual classification response
                # print(f"\n💬 OPENAI CLASSIFICATION RESPONSE #{original_index + 1}:")
                # print(f"{'-'*60}")
                # print(response_text)
                # print(f"{'-'*60}")
                
                # Extract JSON from response
                try:
                    # Try to find JSON in the response
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_str = response_text[start_idx:end_idx + 1]
                        result = json.loads(json_str)
                        result['original_index'] = original_index
                        result['name'] = name
                        return result
                    else:
                        # Fallback: assume it's a medicine if unclear
                        return {
                            "is_medicine": True,
                            "classification": "medicine", 
                            "reason": "classification unclear",
                            "original_index": original_index,
                            "name": name
                        }
                except json.JSONDecodeError:
                    # Fallback for JSON parsing errors
                    is_medicine = "true" in response_text.lower() or "medicine" in response_text.lower()
                    return {
                        "is_medicine": is_medicine,
                        "classification": "medicine" if is_medicine else "other",
                        "reason": "parsed from text",
                        "original_index": original_index,
                        "name": name
                    }
                    
            except Exception as e:
                print(f"Single name classification failed for '{name}': {e}")
                # Be permissive on errors - assume it's a medicine
                return {
                    "is_medicine": True,
                    "classification": "medicine",
                    "reason": "error fallback",
                    "original_index": original_index,
                    "name": name
                }

        try:
            # Create list of (name, index) pairs for parallel processing
            name_index_pairs = [(name, i) for i, name in enumerate(drug_names)]
            
            # Process all names in parallel - maximum parallelization!
            max_workers = min(len(drug_names), 8)  # Limit to 8 concurrent API calls
            decisions = {}
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all classification tasks
                future_to_name = {
                    executor.submit(_classify_single_name, name_pair): name_pair 
                    for name_pair in name_index_pairs
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_name, timeout=45):  # 45 second total timeout
                    try:
                        result = future.result(timeout=10)  # 10 second per-call timeout
                        if result and 'original_index' in result:
                            decisions[result['original_index']] = result
                    except Exception as e:
                        name_pair = future_to_name.get(future, ('unknown', -1))
                        print(f"Parallel classification failed for '{name_pair[0]}': {e}")
                        # Add permissive fallback for failed calls
                        if name_pair[1] >= 0:
                            decisions[name_pair[1]] = {
                                "is_medicine": True,
                                "classification": "medicine",
                                "reason": "timeout fallback",
                                "original_index": name_pair[1],
                                "name": name_pair[0]
                            }

            processing_time = (datetime.now() - start_time).total_seconds()
            # print(f"Parallel LLM classification completed in {processing_time:.2f}s for {len(drug_names)} names")
            
            # 🔍 CONSOLE LOG: Show detailed classification results for each item
            # print(f"\n📊 DETAILED CLASSIFICATION RESULTS:")
            print(f"{'='*80}")
            for i, name in enumerate(drug_names):
                decision = decisions.get(i)
                if decision:
                    is_med = "MEDICINE" if decision.get('is_medicine') else "NOT MEDICINE"
                    classification = decision.get('classification', 'unknown')
                    reason = decision.get('reason', 'no reason')
                    print(f"  {i+1:2d}. {name:<30} → {is_med} ({classification}) - {reason}")
                else:
                    print(f"  {i+1:2d}. {name:<30} -> MEDICINE (no decision - kept by default)")
            print(f"{'='*80}")

            if not decisions:
                print("LLM classification returned no valid decisions. Skipping filter.")
                return alternatives

            # Apply decisions to filter alternatives
            filtered: List[Dict[str, Any]] = []
            for i, alt in enumerate(alternatives):
                decision = decisions.get(i)
                # If no decision, be permissive and keep
                keep = True
                if decision is not None:
                    keep = bool(decision.get('is_medicine', True))
                    # Annotate validation details for transparency
                    ai_val = alt.setdefault('ai_validation', {})
                    ai_val['is_medicine_name'] = bool(decision.get('is_medicine', True))
                    ai_val['name_classification'] = decision.get('classification', 'medicine')
                    ai_val['classification_reason'] = decision.get('reason', 'no reason')
                    ai_val['processing_time'] = processing_time

                if keep:
                    filtered.append(alt)

            # Removed safety guard - always trust LLM classification results
            print(f"🔍 LLM Name Check: {len(filtered)}/{len(alternatives)} items classified as medicines and kept (in {processing_time:.2f}s)")
            return filtered

        except Exception as e:
            print(f"Parallel LLM medicine-name classification failed: {e}. Returning all alternatives for safety.")
            return alternatives

    def _generate_suitable_tags(self, alternative: Dict[str, Any], therapeutic_info: Dict[str, Any]) -> List[str]:
        """Generate suitable tags for alternative medications based on their properties."""
        tags = []
        
        # Match type based tags
        match_type = alternative.get('match_type', 'unknown')
        if match_type == 'exact_ingredient':
            tags.append('Same Active Ingredient')
        elif match_type == 'therapeutic_equivalent':
            tags.append('Therapeutic Equivalent')
        elif match_type == 'partial_match':
            tags.append('Related Medication')
        
        # Similarity score based tags
        similarity = alternative.get('combined_similarity', 0)
        if similarity >= 0.9:
            tags.append('Highly Similar')
        elif similarity >= 0.8:
            tags.append('Good Match')
        elif similarity >= 0.5:
            tags.append('Moderate Match')
        else:
            tags.append('Low Similarity')
        
        # Drug name type tags
        drug_name = alternative.get('drug_name', '').lower()
        generic_name = alternative.get('generic_name', '').lower()
        
        # Check if it's likely a generic vs brand name
        if drug_name and generic_name:
            # Common brand name patterns (usually capitalized, shorter)
            if len(drug_name) < len(generic_name) and drug_name[0].isupper():
                tags.append('Brand Name')
            else:
                tags.append('Generic Available')
        
        # Formulary status tags (if available in data)
        if 'tier' in alternative or 'formulary_tier' in alternative:
            tier = alternative.get('tier') or alternative.get('formulary_tier', '')
            if tier:
                if '1' in str(tier):
                    tags.append('Tier 1 - Preferred')
                elif '2' in str(tier):
                    tags.append('Tier 2 - Standard')
                elif '3' in str(tier):
                    tags.append('Tier 3 - Non-Preferred')
                else:
                    tags.append(f'Tier {tier}')
        
        # Coverage status tags
        if 'coverage_status' in alternative:
            status = alternative.get('coverage_status', '').lower()
            if 'covered' in status:
                tags.append('Covered')
            elif 'not covered' in status:
                tags.append('Not Covered')
            elif 'prior authorization' in status or 'pa' in status:
                tags.append('Prior Authorization Required')
            elif 'quantity limit' in status or 'ql' in status:
                tags.append('Quantity Limited')
        
        # Special medication class tags based on drug name patterns
        drug_name_lower = drug_name.lower()
        
        # Diabetes medications
        diabetes_indicators = ['insulin', 'metformin', 'ozempic', 'wegovy', 'trulicity', 'januvia', 'jardiance', 'farxiga']
        if any(indicator in drug_name_lower for indicator in diabetes_indicators):
            tags.append('Diabetes Medication')
        
        # Blood pressure medications
        bp_indicators = ['lisinopril', 'losartan', 'amlodipine', 'atenolol', 'metoprolol']
        if any(indicator in drug_name_lower for indicator in bp_indicators):
            tags.append('Blood Pressure')
        
        # Cholesterol medications
        cholesterol_indicators = ['atorvastatin', 'simvastatin', 'rosuvastatin', 'lipitor', 'crestor']
        if any(indicator in drug_name_lower for indicator in cholesterol_indicators):
            tags.append('Cholesterol')
        
        # Heart medications
        heart_indicators = ['warfarin', 'coumadin', 'eliquis', 'xarelto']
        if any(indicator in drug_name_lower for indicator in heart_indicators):
            tags.append('Heart Medication')
        
        # Antidepressants
        depression_indicators = ['sertraline', 'fluoxetine', 'citalopram', 'escitalopram', 'zoloft', 'prozac']
        if any(indicator in drug_name_lower for indicator in depression_indicators):
            tags.append('Antidepressant')
        
        # Pain medications
        pain_indicators = ['ibuprofen', 'naproxen', 'acetaminophen', 'tramadol', 'gabapentin']
        if any(indicator in drug_name_lower for indicator in pain_indicators):
            tags.append('Pain Relief')
        
        # Antibiotics
        antibiotic_indicators = ['amoxicillin', 'azithromycin', 'ciprofloxacin', 'doxycycline', 'cephalexin']
        if any(indicator in drug_name_lower for indicator in antibiotic_indicators):
            tags.append('Antibiotic')
        
        # Injectable vs oral
        if 'injection' in drug_name_lower or 'pen' in drug_name_lower or 'insulin' in drug_name_lower:
            tags.append('Injectable')
        else:
            tags.append('Oral Medication')
        
        # Frequency/dosing tags (if available in metadata)
        if 'once daily' in str(alternative).lower() or 'daily' in drug_name_lower:
            tags.append('Once Daily')
        elif 'twice' in str(alternative).lower():
            tags.append('Twice Daily')
        
        # Cost-related tags
        if similarity >= 0.8 and match_type == 'exact_ingredient':
            tags.append('Cost-Effective Alternative')
        
        # Remove duplicates and limit to most relevant tags
        unique_tags = list(dict.fromkeys(tags))  # Preserves order while removing duplicates
        
        # Return top 6 most relevant tags
        return unique_tags[:6]
    
    def _finalize_clean_drug_name(self, drug_name: str) -> Optional[str]:
        """
        Final cleaning/validation step before embedding.
        Ensures no junk names like 'ql', 'mg', 'italic' get stored.
        Returns None if the name is invalid.
        """
        if not drug_name:
            return None

        name = drug_name.strip()

        # Normalize capitalization
        name = name.title()

        # Explicitly reject common junk tokens
        junk_tokens = {"ql", "mg", "mcg", "ml", "italic", "tab", "inj"}
        if name.lower() in junk_tokens:
            return None

        # Reject very short meaningless entries
        if len(name) <= 2 and name.lower() not in {"iv"}:
            return None

        # Ensure it passes the existing validity check
        if not self._is_valid_drug_name(name):
            return None

        return name

    def _normalize_medicine_form(self, form: str) -> str:
        """
        Normalize medicine form with same logic as Pydantic model.
        Fallback to 'Not Specified' for invalid/missing forms.
        """
        if not form or isinstance(form, str) and form.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            return "Not Specified"
        
        cleaned = str(form).strip()
        
        # Handle problematic values
        if cleaned.lower() in ['same', 'unknown', 'unclear', 'not specified', 'none']:
            return "Not Specified"
            
        # Handle generic descriptors
        generic_descriptors = {'various', 'multiple', 'all forms', 'different strengths', 'assorted', 'mixed', 'unspecified', 'combination form'}
        if cleaned.lower() in generic_descriptors:
            return "Not Specified"
        
        # Try to standardize common forms
        form_mapping = {
            'tab': 'Tablet', 'tabs': 'Tablet', 'tablet': 'Tablet',
            'cap': 'Capsule', 'caps': 'Capsule', 'capsule': 'Capsule',
            'inj': 'Injection', 'injection': 'Injection',
            'iv': 'Intravenous', 'intravenous': 'Intravenous',
            'po': 'Oral', 'oral': 'Oral',
            'top': 'Topical', 'topical': 'Topical',
            'cr': 'Cream', 'cream': 'Cream',
            'oint': 'Ointment', 'ointment': 'Ointment',
            'sol': 'Solution', 'solution': 'Solution',
            'susp': 'Suspension', 'suspension': 'Suspension',
            'syr': 'Syrup', 'syrup': 'Syrup',
            'drops': 'Drops', 'spray': 'Spray', 'patch': 'Patch',
            'gel': 'Gel', 'inhaler': 'Inhaler', 'suppository': 'Suppository',
            'lotion': 'Lotion', 'powder': 'Powder', 'shampoo': 'Shampoo',
        }
        
        cleaned_lower = cleaned.lower().strip()
        if cleaned_lower in form_mapping:
            return form_mapping[cleaned_lower]
        
        # Check if it contains any valid forms
        valid_forms = [
            "Tablet", "Capsule", "Injection", "Intravenous", "Oral", "Topical", 
            "Cream", "Ointment", "Solution", "Suspension", "Syrup", "Drops", 
            "Spray", "Patch", "Gel", "Inhaler", "Suppository", "Lotion", 
            "Powder", "Oral Concentrate", "Oral Solution", "External Cream",
            "External Ointment", "Nasal Spray", "Eye Drops", "Ear Drops",
            "Sublingual", "Buccal", "Rectal", "Vaginal",
        ]
        
        for valid_form in valid_forms:
            if valid_form.lower() in cleaned_lower or cleaned_lower in valid_form.lower():
                return valid_form
        
        # If no match found, default to Not Specified
        return "Not Specified"

    def _group_medicines_by_base_name(self, medicines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Group medicines by their base drug name and combine all forms into a single entry.
        
        For example:
        - Multiple 'lidocaine' entries with different forms (injection, gel, solution) 
          become one 'lidocaine' entry with all forms listed
        - Multiple 'lidocaine hcl' entries become one 'lidocaine hcl' entry with all forms
        
        Args:
            medicines: List of medicine dictionaries
            
        Returns:
            List of grouped medicine dictionaries with combined forms
        """
        if not medicines:
            return []
        
        # Group medicines by normalized drug name
        grouped = {}
        
        for medicine in medicines:
            drug_name = medicine.get('drug_name', '').strip()
            if not drug_name:
                continue
                
            # Use the original drug name as the key (not normalized) to preserve exact names
            base_key = drug_name.lower()
            
            if base_key not in grouped:
                # First occurrence - create the base entry
                grouped[base_key] = medicine.copy()
                # Initialize the forms list with current form (normalize to title case)
                raw_form = medicine.get('medicine_form') or medicine.get('dosage_form', '')
                current_form = self._normalize_medicine_form(raw_form)
                
                grouped[base_key]['all_medicine_forms'] = [current_form]
                grouped[base_key]['_forms_lowercase'] = [current_form.lower()]  # Track lowercase for comparison
                grouped[base_key]['form_count'] = 1
            else:
                # Additional occurrence - add the form to existing entry
                existing_entry = grouped[base_key]
                raw_form = medicine.get('medicine_form') or medicine.get('dosage_form', '')
                current_form = self._normalize_medicine_form(raw_form)
                
                # Check if this form already exists (case-insensitive)
                form_lowercase = current_form.lower()
                if form_lowercase not in existing_entry.get('_forms_lowercase', []):
                    existing_entry['all_medicine_forms'].append(current_form)
                    existing_entry.setdefault('_forms_lowercase', []).append(form_lowercase)
                
                existing_entry['form_count'] += 1
                
                # Combine other fields if they have more information
                for field in ['strength', 'tier', 'restrictions', 'therapeutic_class']:
                    existing_value = existing_entry.get(field, '')
                    new_value = medicine.get(field, '')
                    if new_value and new_value != existing_value:
                        if existing_value:
                            # Combine values with separator if both exist and are different
                            combined = f"{existing_value}, {new_value}"
                            if combined not in existing_entry[field]:
                                existing_entry[field] = combined
                        else:
                            existing_entry[field] = new_value
        
        # Convert grouped dictionary back to list and set primary medicine_form
        result = []
        for grouped_medicine in grouped.values():
            forms = grouped_medicine.get('all_medicine_forms', [])
            if forms:
                # Set the primary form to the first one, and keep all forms in all_medicine_forms
                grouped_medicine['medicine_form'] = forms[0]
                grouped_medicine['dosage_form'] = forms[0]
                # Join all forms for display (now properly deduplicated and normalized)
                grouped_medicine['forms_display'] = ', '.join(forms)
            else:
                grouped_medicine['medicine_form'] = 'Not Specified'
                grouped_medicine['dosage_form'] = 'Not Specified'
                grouped_medicine['forms_display'] = 'Not Specified'
                grouped_medicine['all_medicine_forms'] = ['Not Specified']
            
            # Clean up internal tracking field
            grouped_medicine.pop('_forms_lowercase', None)
            
            result.append(grouped_medicine)
        
        # Sort by drug name for consistent ordering
        result.sort(key=lambda x: x.get('drug_name', '').lower())
        
        return result


    def simple_search_drug(self, drug_name: str) -> list:
        """Enhanced drug search with strict matching and suggestions for close matches."""
        results = []
        suggestions = []
        search_name = drug_name.lower().strip()
        
        # Normalize the search name to handle salt forms
        normalized_search_name = self._normalize_drug_name_for_comparison(drug_name)

        # MODIFIED: More permissive validation - only exclude empty/very short names
        if not search_name or len(search_name) < 2:
            #print(f"⚠️ Invalid drug name: '{drug_name}' is too short")
            return []

        #print(f"🔍 Searching for: '{drug_name}' in database with {len(self.drug_database)} active ingredients")

        # 1. Exact match (case-insensitive) - including normalized matching
        for ingredient, drugs in self.drug_database.items():
            for drug in drugs:
                dn = drug.get('drug_name', '').lower().strip()
                gn = drug.get('generic_name', '').lower().strip()
                
                # Get normalized versions for comparison
                normalized_dn = self._normalize_drug_name_for_comparison(drug.get('drug_name', ''))
                normalized_gn = self._normalize_drug_name_for_comparison(drug.get('generic_name', ''))
                
                # Check for exact match with original or normalized names
                if (search_name == dn or search_name == gn or 
                    normalized_search_name == normalized_dn or normalized_search_name == normalized_gn):
                    
                    # MODIFIED: More permissive validation - show all matches including duplicates
                    if drug.get('drug_name', '') and len(drug.get('drug_name', '').strip()) >= 2:
                        results.append(drug)
                        #print(f"✅ Exact match found: {drug.get('drug_name', 'N/A')}")
                    else:
                        #print(f"⚠️ Filtered out invalid exact match: {drug.get('drug_name', 'N/A')}")
                        pass

        if results:
            # Group medicines by base name before returning
            return self._group_medicines_by_base_name(results)

        # 2. Prefix match for partial input - including normalized matching
        for ingredient, drugs in self.drug_database.items():
            for drug in drugs:
                dn = drug.get('drug_name', '').lower().strip()
                gn = drug.get('generic_name', '').lower().strip()
                
                # Get normalized versions for comparison
                normalized_dn = self._normalize_drug_name_for_comparison(drug.get('drug_name', ''))
                normalized_gn = self._normalize_drug_name_for_comparison(drug.get('generic_name', ''))
                
                # Check for prefix match with original or normalized names
                if (dn.startswith(search_name) or gn.startswith(search_name) or
                    normalized_dn.startswith(normalized_search_name) or normalized_gn.startswith(normalized_search_name)):
                    
                    # MODIFIED: More permissive validation - show all matches including duplicates
                    if drug.get('drug_name', '') and len(drug.get('drug_name', '').strip()) >= 2:
                        results.append(drug)
                        #print(f"📍 Prefix match found: {drug.get('drug_name', 'N/A')}")
                    else:
                        #print(f"⚠️ Filtered out invalid prefix match: {drug.get('drug_name', 'N/A')}")
                        pass

        if results:
            # Group medicines by base name before returning
            return self._group_medicines_by_base_name(results)

        # 3. Fuzzy matching for suggestions
        #print(f"🎯 Trying fuzzy matching for suggestions...")
        threshold = 0.9 if len(search_name) <= 5 else 0.8
        close_matches = difflib.get_close_matches(search_name, self.all_drug_names, n=5, cutoff=threshold)
        
        # Also try fuzzy matching with normalized search name
        normalized_close_matches = difflib.get_close_matches(normalized_search_name, 
                                                           [self._normalize_drug_name_for_comparison(name) for name in self.all_drug_names], 
                                                           n=5, cutoff=threshold)
        
        # Convert normalized matches back to original names
        for norm_match in normalized_close_matches:
            for orig_name in self.all_drug_names:
                if self._normalize_drug_name_for_comparison(orig_name) == norm_match:
                    if orig_name.lower() not in close_matches:
                        close_matches.append(orig_name.lower())
        
        seen_suggestion_names = set()
        for match in close_matches:
            for ingredient, drugs in self.drug_database.items():
                for drug in drugs:
                    dn = drug.get('drug_name', '').lower().strip()
                    gn = drug.get('generic_name', '').lower().strip()
                    
                    if match == dn or match == gn:
                        # Validate the drug name before adding to suggestions - show all matches including duplicates
                        if drug.get('drug_name', '') and len(drug.get('drug_name', '').strip()) >= 2:
                            suggestions.append(drug)
                            #print(f"💡 Suggestion: {drug.get('drug_name', 'N/A')}")
                        else:
                            #print(f"⚠️ Filtered out invalid suggestion: {drug.get('drug_name', 'N/A')}")
                            pass

        if suggestions:
            for drug in suggestions:
                drug['is_suggestion'] = True
            # Group suggestions by base name before returning
            return self._group_medicines_by_base_name(suggestions)

        # 4. Vector search for alternative names (if available)
        if self.retriever and not results and not suggestions:
            #print(f"🔎 Searching in vector embeddings for alternative names...")
            try:
                # Search specifically in alternative names field
                vector_query = f"Alternative names: {drug_name}"
                vector_docs = self.retriever.invoke(vector_query)
                
                # Extract drug information from vector search results
                for doc in vector_docs:
                    metadata = doc.metadata
                    if metadata and 'drug_name' in metadata:
                        drug_name_from_vector = metadata.get('drug_name', '')
                        if drug_name_from_vector and len(drug_name_from_vector.strip()) >= 2:
                            # Find the full drug entry in our database
                            for ingredient, drugs in self.drug_database.items():
                                for drug in drugs:
                                    if drug.get('drug_name', '').lower() == drug_name_from_vector.lower():
                                        drug['vector_match'] = True  # Mark as found via vector search
                                        results.append(drug)
                                        #print(f"🎯 Vector match found: {drug.get('drug_name', 'N/A')}")
                                        break
                
                if results:
                    # Group medicines by base name before returning
                    return self._group_medicines_by_base_name(results)
                    
            except Exception as e:
                #print(f"⚠️ Vector search failed: {str(e)}")
                pass

        # 5. Search in raw text as a last resort
        if self.raw_text_content:
            #print(f"🔎 Searching in raw PDF text...")
            raw_matches = self._search_in_raw_text(drug_name)
            if raw_matches:
                results.extend(raw_matches)
                # Group medicines by base name before returning
                return self._group_medicines_by_base_name(results)

        return []

    def search_by_alternative_names(self, drug_name: str) -> List[Dict[str, Any]]:
        """Optimized search for drugs using vector embeddings with caching and smart query selection."""
        if not self.retriever:
            return []
        
        # Check cache first
        cache_key = self._get_cache_key('alt_names', drug_name.lower())
        cached_result = self._get_from_cache(self.search_cache, cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # Smart query selection - prioritize most effective queries
            base_queries = [
                f"Alternative names: {drug_name}",
                f"{drug_name} brand name generic equivalent"
            ]
            
            # Add additional queries only for complex drug names
            if len(drug_name.split()) > 1 or any(char in drug_name for char in ['-', '_']):
                base_queries.extend([
                    f"Drug name {drug_name} alternative",
                    f"Medication {drug_name}"
                ])
            
            found_drugs = []
            
            # Execute queries in parallel with optimized thread count
            def execute_query_cached(query):
                """Execute query with embedding caching."""
                query_cache_key = self._get_cache_key('query', query)
                cached_query_result = self._get_from_cache(self.embedding_cache, query_cache_key)
                
                if cached_query_result is not None:
                    return query, cached_query_result
                
                try:
                    docs = self.retriever.invoke(query)
                    self._set_cache(self.embedding_cache, query_cache_key, docs)
                    return query, docs
                except Exception as e:
                    #print(f"⚠️ Alternative name search query failed: {query} - {str(e)}")
                    return query, []
            
            # Use dynamic thread count based on query complexity
            thread_count = min(len(base_queries), self.max_workers // 2)
            
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                # Submit all queries for parallel execution
                query_futures = [executor.submit(execute_query_cached, query) for query in base_queries]
                
                # Process results as they complete
                for future in as_completed(query_futures):
                    try:
                        query, docs = future.result()
                        for doc in docs:
                            metadata = doc.metadata
                            if metadata and 'drug_name' in metadata:
                                drug_name_found = metadata.get('drug_name', '')
                                drug_key = drug_name_found.lower()
                                
                                # MODIFIED: Show all matches including duplicates - only check minimum length
                                if (drug_name_found and 
                                    len(drug_name_found.strip()) >= 2):  # Only check minimum length
                                    
                                    # Create drug entry from metadata
                                    drug_entry = {
                                        'drug_name': metadata.get('drug_name', ''),
                                        'generic_name': metadata.get('generic_name', ''),
                                        'active_ingredient': metadata.get('active_ingredient', ''),
                                        'therapeutic_class': metadata.get('therapeutic_class', ''),
                                        'tier': metadata.get('tier', ''),
                                        'restrictions': metadata.get('restrictions', ''),
                                        'dosage_form': metadata.get('dosage_form', ''),
                                        'strength': metadata.get('strength', ''),
                                        'source_document': metadata.get('source_document', ''),
                                        'found_via': 'alternative_names_vector_search',
                                        'search_query': query
                                    }
                                    found_drugs.append(drug_entry)
                    except Exception as e:
                        #print(f"⚠️ Alternative name search query processing failed: {str(e)}")
                        pass
            
            # Cache the results
            self._set_cache(self.search_cache, cache_key, found_drugs)
            
            if found_drugs:
                #print(f"🎯 Found {len(found_drugs)} drugs via alternative names vector search")
                # Group medicines by base name before returning
                return self._group_medicines_by_base_name(found_drugs)
            
            return []
            
        except Exception as e:
            #print(f"❌ Error in alternative names search: {str(e)}")
            return []

    def _search_in_raw_text(self, drug_name: str) -> List[Dict[str, Any]]:
        """Search for drug mentions in raw text content with better precision."""
        results = []
        if not self.raw_text_content:
            return results

        lines = self.raw_text_content.split('\n')
        drug_name_lower = drug_name.lower()
        word_pattern = r'\b' + re.escape(drug_name_lower) + r'\b'

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if re.search(word_pattern, line_lower):
                context_lines = lines[max(0, i-2):min(len(lines), i+3)]
                context = ' '.join(context_lines)

                drug_match = re.search(r'\b' + re.escape(drug_name_lower) + r'\w*\b', line_lower)
                actual_drug_name = line[drug_match.start():drug_match.end()] if drug_match else drug_name

                # Validate the found drug name before processing
                if not self._is_valid_drug_name(actual_drug_name):
                    #print(f"⚠️ Filtered out invalid drug name from raw text: '{actual_drug_name}'")
                    continue

                tier_match = re.search(r'tier\s*([1-5])|t([1-5])|\b([1-5])\s*tier', context.lower())
                tier = f"Tier {tier_match.group(1) or tier_match.group(2) or tier_match.group(3)}" if tier_match else "Unknown"

                restrictions = []
                if re.search(r'\bPA\b|prior\s*auth', context, re.IGNORECASE):
                    restrictions.append('PA')
                if re.search(r'\bST\b|step\s*therapy', context, re.IGNORECASE):
                    restrictions.append('ST')
                if re.search(r'\bQL\b|quantity\s*limit', context, re.IGNORECASE):
                    restrictions.append('QL')

                dosage_forms = self.dynamic_dosage_forms if self.dynamic_dosage_forms else [
                    'tablet', 'capsule', 'injection', 'cream', 'ointment', 'solution', 
                    'syrup', 'drops', 'oral'
                ]
                dosage_form = 'None'
                for form in dosage_forms:
                    if form in context.lower():
                        dosage_form = form.title()
                        break

                strength_match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%)', context, re.IGNORECASE)
                strength = strength_match.group(0) if strength_match else 'None'

                drug_entry = {
                    'drug_name': actual_drug_name.title(),
                    'generic_name': actual_drug_name.title(),
                    'active_ingredient': actual_drug_name.lower(),
                    'tier': tier,
                    'restrictions': ', '.join(restrictions) if restrictions else 'None',
                    'dosage_form': dosage_form,
                    'strength': strength,
                    'source_document': 'PDF_Raw_Text',
                    'found_in_line': line.strip()[:200],
                    'search_method': 'raw_text_search'
                }
                results.append(drug_entry)
                #print(f"📄 Found '{actual_drug_name}' in raw text: {line.strip()[:100]}...")

        return results

    def load_formulary_documents(self, document_paths: Union[str, List[str]]) -> List[Document]:
        """
        Load multiple formulary documents (PDF, DOCX, TXT, CSV).
        """
        if isinstance(document_paths, str):
            document_paths = [document_paths]

        all_documents = []

        for doc_path in document_paths:
            if not os.path.exists(doc_path):
                logger.warning(f"Document not found: {doc_path}")
                continue

            try:
                documents = self._process_single_document(doc_path)
                all_documents.extend(documents)
                logger.info(f"Processed {len(documents)} chunks from {doc_path}")
            except Exception as e:
                logger.error(f"Error processing {doc_path}: {str(e)}")
                continue  # Skip the document if processing fails

        self._update_drug_names_cache()
        logger.info(f"Total documents loaded: {len(all_documents)}")
        return all_documents

    def _update_drug_names_cache(self):
        """Update the cache of all drug names for autocomplete."""
        self.all_drug_names = []
        for ingredient, drugs in self.drug_database.items():
            for drug in drugs:
                dn = drug.get('drug_name', '').strip()
                gn = drug.get('generic_name', '').strip()
                
                # Only cache valid drug names
                if dn and self._is_valid_drug_name(dn) and dn not in self.all_drug_names:
                    self.all_drug_names.append(dn)
                if gn and self._is_valid_drug_name(gn) and gn not in self.all_drug_names:
                    self.all_drug_names.append(gn)
                    
        logger.info(f"Cached {len(self.all_drug_names)} validated drug names for autocomplete")

    def _process_single_document(self, doc_path: str) -> List[Document]:
        """
        Process a single document (PDF, TXT, CSV) and extract drug entries.
        """
        file_extension = Path(doc_path).suffix.lower()
        documents = []

        if file_extension == '.pdf':
            # COMPREHENSIVE APPROACH: Extract medicine forms using both comprehensive list and dynamic extraction
            print(f"🔄 Initializing comprehensive medicine form extraction for {Path(doc_path).name}")
            self.comprehensive_forms_list = self.get_comprehensive_medicine_forms(doc_path)
            
            # Use enhanced PDF processor
            if self.enhanced_pdf_processor is None:
                # Initialize with the directory containing the PDF
                pdf_dir = str(Path(doc_path).parent)
                self.enhanced_pdf_processor = EnhancedPDFProcessor(data_folder=pdf_dir)
            
            # Get the filename and extract content
            filename = Path(doc_path).name
            text = self.enhanced_pdf_processor.get_pdf_content(filename)
            
            if not text:
                logger.warning(f"No text extracted from {doc_path} using enhanced processor")
                # Fallback to old method if enhanced processor fails
                text = self._extract_pdf_text(doc_path)
                
            self.raw_text_content += text + "\n"
            drug_entries = self._parse_text_to_drug_entries(text, doc_path, self.enable_llm_prevalidation)
            for entry in drug_entries:
                content = self._create_drug_content_from_entry(entry)
                doc = Document(
                    page_content=content,
                    metadata={
                        'source_document': Path(doc_path).name,
                        'drug_name': entry.get('drug_name', ''),
                        'medicine_name': entry.get('drug_name', ''),  # Explicit medicine name field
                        'generic_name': entry.get('generic_name', ''),
                        'active_ingredient': entry.get('active_ingredient', ''),
                        'therapeutic_class': entry.get('therapeutic_class', ''),
                        'tier': entry.get('tier', ''),
                        'restrictions': entry.get('restrictions', ''),
                        'dosage_form': entry.get('dosage_form', ''),
                        'medicine_form': entry.get('medicine_form', entry.get('dosage_form', '')),  # Explicit medicine form field
                        'strength': entry.get('strength', ''),
                        'entry_type': 'formulary_drug'
                    }
                )
                documents.append(doc)
            self._update_drug_database(drug_entries, Path(doc_path).name)

        elif file_extension == '.txt':
            text = self._extract_txt_text(doc_path)
            self.raw_text_content += text + "\n"
            drug_entries = self._parse_text_to_drug_entries(text, doc_path, self.enable_llm_prevalidation)
            for entry in drug_entries:
                content = self._create_drug_content_from_entry(entry)
                doc = Document(
                    page_content=content,
                    metadata={
                        'source_document': Path(doc_path).name,
                        'drug_name': entry.get('drug_name', ''),
                        'medicine_name': entry.get('drug_name', ''),  # Explicit medicine name field
                        'generic_name': entry.get('generic_name', ''),
                        'active_ingredient': entry.get('active_ingredient', ''),
                        'therapeutic_class': entry.get('therapeutic_class', ''),
                        'tier': entry.get('tier', ''),
                        'restrictions': entry.get('restrictions', ''),
                        'dosage_form': entry.get('dosage_form', ''),
                        'medicine_form': entry.get('medicine_form', entry.get('dosage_form', '')),  # Explicit medicine form field
                        'strength': entry.get('strength', ''),
                        'entry_type': 'formulary_drug'
                    }
                )
                documents.append(doc)
            self._update_drug_database(drug_entries, Path(doc_path).name)

        elif file_extension == '.csv':
            documents = self._process_csv_formulary(doc_path)
            drug_entries = [self._parse_csv_row_to_drug_entry(row) for _, row in pd.read_csv(doc_path).iterrows()]
            drug_entries = [entry for entry in drug_entries if entry]
            self._update_drug_database(drug_entries, Path(doc_path).name)

        else:
            logger.warning(f"Unsupported file type: {file_extension}")
            return []

        return documents

    def _enhance_drug_entry_with_ai(self, drug_name: str, context: str) -> Dict[str, str]:
        """Use AI to enhance drug entry with proper generic name and active ingredient."""
        
        # If AI enhancement is disabled, use basic information
        if not self.enable_ai_enhancement:
            #print(f"📝 Using basic info for {drug_name} (AI enhancement disabled)")
            return {
                'generic_name': drug_name,
                'active_ingredient': drug_name.lower(),
                'therapeutic_class': 'Unknown'
            }
        
        # Use AI for comprehensive drug information lookup
        try:
            enhancement_prompt = ChatPromptTemplate.from_template("""
You are a pharmaceutical expert with access to comprehensive drug information. 
Given a drug name, provide the most accurate and up-to-date information about its active ingredient and generic name in JSON format.

Drug Name: {drug_name}
Context (if available): {context}

Please provide information for this drug, considering it might be:
- A brand name with a generic equivalent
- A generic name itself
- A new or specialty medication
- A combination drug with multiple active ingredients

IMPORTANT: Use your pharmaceutical knowledge to identify the correct active ingredient, even if it's a newer medication.

Return ONLY a valid JSON object with no extra text, explanations, or formatting:

{{
    "generic_name": "exact generic name (active ingredient name)",
    "active_ingredient": "active ingredient in lowercase", 
    "therapeutic_class": "specific drug class or mechanism of action",
    "indication": "primary medical condition treated"
}}

Examples of JSON responses:
- Ozempic: {{"generic_name": "Semaglutide", "active_ingredient": "semaglutide", "therapeutic_class": "GLP-1 receptor agonist", "indication": "Type 2 diabetes mellitus"}}
- Zepbound: {{"generic_name": "Tirzepatide", "active_ingredient": "tirzepatide", "therapeutic_class": "GLP-1/GIP receptor agonist", "indication": "Weight management"}}

Return JSON response for {drug_name}:
""")
            
            enhancement_chain = enhancement_prompt | self.llm | StrOutputParser()
            response = enhancement_chain.invoke({
                "drug_name": drug_name,
                "context": context[:500]  # Limit context to avoid token limits
            })
            
            # Clean and parse the response
            response = response.strip()
            # Remove any markdown code block formatting
            if response.startswith('```'):
                lines = response.split('\n')
                for i, line in enumerate(lines):
                    if line.strip().startswith('{'):
                        response = '\n'.join(lines[i:])
                        break
            if response.endswith('```'):
                response = response.rsplit('\n```', 1)[0]
            
            # Try to find JSON in the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                enhanced_info = json.loads(json_str)
                
                # CLEAN the AI response to avoid "same" issues
                generic_name = enhanced_info.get('generic_name', drug_name)
                if generic_name.lower() in ['same', 'unknown', 'unclear', 'not specified']:
                    generic_name = drug_name
                
                active_ingredient = enhanced_info.get('active_ingredient', drug_name.lower())
                if active_ingredient.lower() in ['same', 'unknown', 'unclear', 'not specified']:
                    active_ingredient = generic_name.lower()
                
                therapeutic_class = enhanced_info.get('therapeutic_class', 'Unknown')
                if therapeutic_class.lower() in ['same', 'unknown', 'unclear', 'not specified']:
                    # Use Pydantic inference as fallback for therapeutic class
                    if PYDANTIC_AVAILABLE:
                        from medicine_models import MedicineEntry
                        inferred_class = MedicineEntry._infer_therapeutic_class(drug_name, generic_name)
                        therapeutic_class = inferred_class if inferred_class != "Unknown" else 'Unknown'
                        print(f"🎯 AI fallback: Inferred therapeutic class '{inferred_class}' for {drug_name}")
                    else:
                        therapeutic_class = 'Unknown'
                
                return {
                    'generic_name': generic_name,
                    'active_ingredient': active_ingredient,
                    'therapeutic_class': therapeutic_class
                }
            else:
                raise ValueError("No valid JSON found in response")
            
        except Exception as e:
            logger.warning(f"AI enhancement failed for {drug_name}: {str(e)}")
            # Enhanced fallback with Pydantic therapeutic class inference
            therapeutic_class = 'Unknown'
            if PYDANTIC_AVAILABLE:
                from medicine_models import MedicineEntry
                inferred_class = MedicineEntry._infer_therapeutic_class(drug_name, drug_name)
                therapeutic_class = inferred_class if inferred_class != "Unknown" else 'Unknown'
                if therapeutic_class != "Unknown":
                    print(f"🎯 Fallback success: Inferred therapeutic class '{therapeutic_class}' for {drug_name}")
            
            return {
                'generic_name': drug_name,
                'active_ingredient': drug_name.lower(),
                'therapeutic_class': therapeutic_class
            }

    def _validate_and_extract_medicines_with_llm(self, text: str, source_file: str) -> List[Dict[str, Any]]:
        """
        🎯 ENHANCED: LLM extraction with structured outputs for guaranteed data quality.
        
        Now uses Pydantic models as response format to force LLM compliance.
        Ensures NO chunks are lost due to timeouts and NO "None" values in output.
        """
        if not text or not self.enable_ai_enhancement:
            return []
        
        print(f"🎯 Using enhanced LLM extraction with structured outputs for {Path(source_file).name}...")
        
        # Use smaller chunks to reduce timeout risk
        text_chunks = [text[i:i+self.chunk_size_for_extraction] for i in range(0, len(text), self.chunk_size_for_extraction)]
        print(f"🚀 Processing {len(text_chunks)} chunks (max {self.chunk_size_for_extraction} chars each) with structured outputs...")
        
        all_validated_medicines = []
        failed_chunks = []  # Track failed chunks for retry
        
        def process_chunk_with_retry(chunk_data, retry_count=0):
            """Process a single chunk with structured outputs and exponential backoff retry."""
            chunk_idx, chunk = chunk_data
            thread_id = threading.current_thread().ident
            
            # Exponential backoff delay for retries
            if retry_count > 0:
                import time
                delay = min(2 ** retry_count, 10)  # Max 10 second delay
                print(f"  🔄 Retry {retry_count} for Chunk {chunk_idx + 1} after {delay}s delay...")
                time.sleep(delay)
            
            print(f"  📦 Chunk {chunk_idx + 1}/{len(text_chunks)} [Thread {thread_id}] (Attempt {retry_count + 1})...")
            
            try:
                # Use NEW structured extraction method for guaranteed data quality
                chunk_medicines = self._extract_medicines_with_structured_llm(chunk, source_file)
                
                if chunk_medicines:
                    print(f"  ✅ Chunk {chunk_idx + 1}: extracted {len(chunk_medicines)} medicines with structured outputs")
                    return chunk_medicines
                else:
                    print(f"  ⚠️ Chunk {chunk_idx + 1}: no medicines found")
                    return []
            except Exception as e:
                error_str = str(e).lower()
                if "timeout" in error_str or "timed out" in error_str:
                    print(f"    ⏰ Chunk {chunk_idx + 1}: Timeout on attempt {retry_count + 1}")
                else:
                    print(f"    ❌ Chunk {chunk_idx + 1}: Error on attempt {retry_count + 1} - {str(e)}")
                
                # Retry if under limit
                if retry_count < self.max_chunk_retries:
                    return process_chunk_with_retry(chunk_data, retry_count + 1)
                else:
                    print(f"    💀 Chunk {chunk_idx + 1}: Max retries exceeded, adding to failed chunks")
                    failed_chunks.append(chunk_data)
                    return []
        
        # Process chunks with reduced parallelism to avoid rate limits
        max_workers = min(self.max_extraction_workers, len(text_chunks))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunk processing jobs with structured outputs
            future_to_chunk = {
                executor.submit(process_chunk_with_retry, (idx, chunk)): (idx, chunk)
                for idx, chunk in enumerate(text_chunks)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                chunk_idx, original_chunk = future_to_chunk[future]
                try:
                    chunk_medicines = future.result(timeout=self.chunk_timeout_seconds + 30)
                    if chunk_medicines:
                        all_validated_medicines.extend(chunk_medicines)
                    else:
                        failed_chunks.append((chunk_idx, original_chunk))
                except Exception as exc:
                    print(f"    💥 Chunk {chunk_idx + 1} generated an exception: {exc}")
                    failed_chunks.append((chunk_idx, original_chunk))
        
        # RECOVERY: Process failed chunks with pattern extraction
        if failed_chunks:
            print(f"🔧 RECOVERY: Processing {len(failed_chunks)} failed chunks with pattern extraction...")
            for chunk_idx, failed_chunk in failed_chunks:
                print(f"  🩹 Recovering Chunk {chunk_idx + 1} with pattern extraction...")
                try:
                    pattern_results = self._parse_text_with_patterns(failed_chunk, source_file)
                    for result in pattern_results:
                        result['extraction_method'] = 'pattern_fallback_after_structured_timeout'
                        result['chunk_index'] = chunk_idx
                    all_validated_medicines.extend(pattern_results)
                    print(f"    🩹 Recovered {len(pattern_results)} medicines from failed Chunk {chunk_idx + 1}")
                except Exception as recovery_error:
                    print(f"    💀 Pattern recovery failed for Chunk {chunk_idx + 1}: {str(recovery_error)}")
        
        success_rate = (len(text_chunks) - len(failed_chunks)) / len(text_chunks) * 100
        print(f"🎯 Structured extraction complete: {len(all_validated_medicines)} medicines with guaranteed data quality")
        print(f"📊 Success rate: {success_rate:.1f}% ({len(text_chunks) - len(failed_chunks)}/{len(text_chunks)} chunks successful)")
        
        return all_validated_medicines

    def _merge_llm_and_pattern_results(self, llm_entries: List[Dict[str, Any]], pattern_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Intelligently merge LLM-validated entries with pattern-based entries to ensure completeness.
        
        Strategy:
        1. Start with all LLM-validated entries (higher quality)
        2. Add all pattern-based entries without duplicate checking (show all results)
        3. Combine both lists for maximum coverage including duplicates
        """
        if not pattern_entries:
            return llm_entries
        if not llm_entries:
            return pattern_entries
            
        print(f"🔗 Merging {len(llm_entries)} LLM entries with {len(pattern_entries)} pattern entries...")
        
        # Create a set of normalized drug names from LLM results for duplicate detection
        llm_drug_names = set()
        for entry in llm_entries:
            drug_name = entry.get('drug_name', '').strip()
            if drug_name:
                normalized_name = self._normalize_drug_name_for_comparison(drug_name)
                llm_drug_names.add(normalized_name)
        
        # Start with all LLM entries
        merged_entries = list(llm_entries)
        
        # Add all pattern entries without duplicate checking - show all results including duplicates
        for pattern_entry in pattern_entries:
            pattern_drug_name = pattern_entry.get('drug_name', '').strip()
            if not pattern_drug_name:
                continue
                
            # Mark as pattern-extracted and add without checking for duplicates
            pattern_entry['extraction_method'] = 'pattern_backup'
            pattern_entry['llm_validated'] = False
            merged_entries.append(pattern_entry)
        
        print(f"📊 Merge complete: {len(llm_entries)} LLM + {len(pattern_entries)} pattern entries = {len(merged_entries)} total medicines")
        return merged_entries

    def _parse_text_to_drug_entries(self, text: str, source_file: str, use_llm_prevalidation: bool = True) -> List[Dict[str, Any]]:
        """
        Enhanced parsing focused on drug entries with priority for structured outputs.
        
        Args:
            text: Text to parse
            source_file: Source filename
            use_llm_prevalidation: If True, use LLM to pre-validate medicines before embedding
            
        Returns:
            List of validated drug entries with proper therapeutic classification
        """
        
        # PRIORITY 1: Use structured LLM extraction if Pydantic models are available
        if PYDANTIC_AVAILABLE and use_llm_prevalidation and self.enable_ai_enhancement:
            print(f"🎯 Using STRUCTURED LLM extraction (Pydantic) for {Path(source_file).name}")
            structured_entries = self._extract_medicines_with_structured_llm(text, source_file)
            
            if structured_entries:
                print(f"✅ Structured extraction successful: {len(structured_entries)} medicines with therapeutic classification")
                
                # Optional: Run pattern-based as backup to catch any missed medicines
                print(f"🔍 Running pattern-based backup to ensure completeness...")
                pattern_entries = self._parse_text_with_patterns(text, source_file)
                
                # Merge intelligently - prefer structured results
                merged_entries = self._merge_llm_and_pattern_results(structured_entries, pattern_entries)
                print(f"📊 Final result: {len(merged_entries)} medicines (structured + pattern backup)")
                return merged_entries
            else:
                print("⚠️ Structured extraction found no medicines, falling back to legacy methods")
        
        # PRIORITY 2: Use LLM pre-validation (legacy method)
        if use_llm_prevalidation and self.enable_ai_enhancement:
            print(f"🧠 Using legacy LLM pre-validation for medicine extraction from {Path(source_file).name}")
            llm_validated_entries = self._validate_and_extract_medicines_with_llm(text, source_file)
            
            # HYBRID APPROACH: Also run pattern-based extraction and merge results
            print(f"🔍 Running pattern-based extraction as backup to ensure completeness...")
            pattern_entries = self._parse_text_with_patterns(text, source_file)
            
            # Merge results intelligently - prefer LLM results but include pattern-only findings
            merged_entries = self._merge_llm_and_pattern_results(llm_validated_entries, pattern_entries)
            
            if merged_entries:
                print(f"✅ Hybrid approach: LLM found {len(llm_validated_entries)}, patterns found {len(pattern_entries)}, merged total: {len(merged_entries)} medicines")
                return merged_entries
            else:
                print("⚠️ Both LLM and pattern extraction found no medicines, using fallback")
        
        # PRIORITY 3: Fallback to pattern-based extraction only (with Pydantic validation if available)
        print(f"🔍 Using pattern-based extraction with enhanced validation for {Path(source_file).name}")
        return self._parse_text_with_patterns(text, source_file)
    
    def _parse_text_with_patterns(self, text: str, source_file: str) -> List[Dict[str, Any]]:
        """Legacy pattern-based parsing method."""
        drug_entries = []
        lines = text.split('\n')
        
        # Enhanced patterns specifically for drug entries matching your formulary format
        drug_line_patterns = [
            r'^C1\s+([A-Z][a-zA-Z\s\-\.]+(?:\([^)]+\))?)\s+[GB]\s+\d+',  # C1 + Drug name + (form) + G/B + tier
            r'^([A-Z][a-zA-Z\s\-\.]+(?:\([^)]+\))?)\s+[GB]\s+\d+',  # Drug name + (form) + G/B + tier (fallback)
            r'^C1\s+([A-Z][^G]*?)\s+G\s+\d+',  # C1 + Drug name (everything before G tier)
            r'^([A-Z][a-zA-Z\s\-\.]+\([^)]+\))\s*$',  # Drug name with form in parentheses at end of line
        ]

        logger.info(f"🔍 Parsing {len(lines)} lines from {Path(source_file).name}")
        
        for line_idx, line in enumerate(lines):
            original_line = line
            line = line.strip()
            
            # Skip empty lines or very short lines
            if not line or len(line) < 5:
                continue
                
            # Enhanced skip patterns for headers and non-drug content
            skip_patterns = [
                r'^page\s+\d+', r'^formulary', r'^tier\s*\d*$', r'^restriction', 
                r'^coverage', r'^copay', r'^prior auth', r'^quantity limit',
                r'^drug name', r'^generic name', r'^\d+$', r'^table', r'^form$',
                r'^strength$', r'^dosage$', r'^various$', r'^unknown$', r'^none$',
                r'^subcutaneous\s+solution$', r'^tablet$', r'^capsule$', r'^injection$',
                r'^solution$', r'^cream$', r'^ointment$', r'^pen$', r'^prefilled$',
                r'^restrictions?$', r'^\d+\s*(mg|mcg|ml|g|%)$', r'^tier\s+[1-5]$',
                r'^pa$', r'^st$', r'^ql$', r'^\d+\.\d+$', r'^drug coverage rules?$',
                r'^covered drugs', r'^category', r'^categories', r'^abuse\s*-?\s*deterrent$',
                r'^handle$', r'^hour$', r'^syringe$', r'^transdermal patch$', r'^lozenge',
                r'^anti-addiction', r'^anesthetics', r'^local anesthetics', r'^analgesics',
                r'^opioid', r'^non-opioid', r'^narcotic', r'^controlled', r'^schedule',
                r'^class\s*[iv]+$', r'^c\d+$', r'^[a-z]\d+$', r'^b\d+$',
                # Category headings and therapeutic classes
                r'^antigout\s+agents?$', r'^anticoagulants?$', r'^antiplatelets?$',
                r'^cardiovascular\s+agents?$', r'^diabetes\s+medications?$',
                r'^respiratory\s+agents?$', r'^gastrointestinal\s+agents?$',
                r'^neurological\s+agents?$', r'^psychiatric\s+medications?$',
                r'^antimicrobials?$', r'^antibiotics?$', r'^antifungals?$',
                r'^antivirals?$', r'^hormones?$', r'^immunosuppressants?$',
                r'^oncology\s+agents?$', r'^pain\s+management$', r'^dermatological?$',
                r'^ophthalmological?$', r'^otolaryngology?$', r'^urological?$',
                r'^\w+\s+agents?$', r'^\w+\s+medications?$', r'^\w+\s+drugs?$'
            ]
            
            # Skip if line matches any exclusion pattern
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
                continue
                
            # Skip lines that are clearly dosage forms or strength descriptions alone
            if re.match(r'^(tablet|capsule|injection|solution|cream|ointment|pen|prefilled|subcutaneous|oral|topical|concentrate|patch|viscous|external|immediate|release|extended)(\s+\w+)*$', line, re.IGNORECASE):
                continue
            
            # Skip lines that are just numbers, letters, or short abbreviations
            if re.match(r'^[A-Z]?\d+$', line.strip()) or len(line.strip()) <= 2:
                continue

            # Look for drug names at the start of lines
            potential_drugs = []
            
            for pattern in drug_line_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    full_drug_text = match.group(1).strip()
                    
                    # Extract drug name and form separately
                    drug_info = self._extract_drug_name_and_form(full_drug_text)
                    clean_drug_name = drug_info["drug_name"].title()
                    medicine_form = drug_info["medicine_form"]
                    
                    if self._is_valid_drug_name(clean_drug_name) and len(clean_drug_name) >= 3:
                        potential_drugs.append({
                            "drug_name": clean_drug_name,
                            "medicine_form": medicine_form,
                            "full_text": full_drug_text
                        })
                        break

            # Also check for capitalized words that might be drug names
            if not potential_drugs:
                # Look for capitalized words at line start
                first_word_match = re.match(r'^([A-Z][A-Za-z\s\-]+(?:\([^)]+\))?)', line)
                if first_word_match:
                    full_drug_text = first_word_match.group(1).strip()
                    
                    # Extract drug name and form separately
                    drug_info = self._extract_drug_name_and_form(full_drug_text)
                    clean_drug_name = drug_info["drug_name"]
                    medicine_form = drug_info["medicine_form"]
                    
                    if self._is_valid_drug_name(clean_drug_name):
                        potential_drugs.append({
                            "drug_name": clean_drug_name,
                            "medicine_form": medicine_form,
                            "full_text": full_drug_text
                        })

            # Process each potential drug
            for drug_info in potential_drugs:
                drug_name = drug_info["drug_name"]
                medicine_form = drug_info["medicine_form"]
                
                # Get extended context for this line
                context_start = max(0, line_idx - 2)
                context_end = min(len(lines), line_idx + 3)
                context = ' '.join(lines[context_start:context_end])
                
                # Enhance with AI/knowledge base for generic name
                enhanced_info = self._enhance_drug_entry_with_ai(drug_name, context)
                
                # Parse formulary information from the line and context
                formulary_info = self._extract_formulary_info_from_context(original_line, context)
                
                # Use the extracted medicine form if available, otherwise use the formulary info
                final_medicine_form = medicine_form if medicine_form else formulary_info.get('dosage_form', 'None')
                
                drug_entry = {
                    'drug_name': drug_name,
                    'generic_name': enhanced_info['generic_name'],
                    'active_ingredient': enhanced_info['active_ingredient'],
                    'therapeutic_class': enhanced_info.get('therapeutic_class', 'Unknown'),
                    'tier': formulary_info.get('tier', 'Unknown'),
                    'restrictions': formulary_info.get('restrictions', 'None'),
                    'dosage_form': final_medicine_form,
                    'medicine_form': final_medicine_form,  # Add explicit medicine_form field
                    'strength': formulary_info.get('strength', 'None'),
                    'source_document': Path(source_file).name,
                    'extraction_method': 'pattern_based'
                }
                
                # CRITICAL: Use Pydantic validation to ensure proper therapeutic class inference
                if PYDANTIC_AVAILABLE:
                    validated_entry = self._validate_medicine_with_pydantic(drug_entry)
                    if validated_entry:
                        drug_entries.append(validated_entry)
                        print(f"✅ Pydantic validated: {validated_entry['drug_name']} -> Therapeutic class: {validated_entry.get('therapeutic_class', 'Unknown')}")
                    else:
                        # Fallback to cleaned data if Pydantic validation fails
                        drug_entry = self._clean_medicine_data(drug_entry)
                        drug_entries.append(drug_entry)
                        print(f"⚠️ Fallback cleaning: {drug_entry['drug_name']} -> {drug_entry.get('therapeutic_class', 'Unknown')}")
                else:
                    # Legacy cleaning if Pydantic not available
                    drug_entry = self._clean_medicine_data(drug_entry)
                    drug_entries.append(drug_entry)
                
                logger.info(f"✅ Extracted: {drug_name} ({final_medicine_form}) -> {drug_entry.get('generic_name', 'unknown')} | Class: {drug_entry.get('therapeutic_class', 'Unknown')}")

        logger.info(f"📊 Extracted {len(drug_entries)} drug entries from {Path(source_file).name}")
        return drug_entries

    def _extract_formulary_info_from_context(self, line: str, context: str) -> Dict[str, str]:
        """Extract formulary-specific information from line and context for your specific format."""
        info = {}
        
        # Extract tier information from patterns like "G 4" or "B 3" (Generic/Brand + tier number)
        tier_match = re.search(r'[GB]\s+(\d+)', line)
        if tier_match:
            tier_number = tier_match.group(1)
            info['tier'] = f"Tier {tier_number}"
        else:
            # Fallback to general tier patterns
            tier_match = re.search(r'tier\s*([1-5])|t([1-5])|\b([1-5])\s*tier', context, re.IGNORECASE)
            info['tier'] = f"Tier {tier_match.group(1) or tier_match.group(2) or tier_match.group(3)}" if tier_match else "Unknown"

        # Extract restrictions from patterns like "7D; MME; DL; QL"
        restrictions = []
        if re.search(r'\bPA\b', line):
            restrictions.append('PA')
        if re.search(r'\bST\b', line):
            restrictions.append('ST')
        if re.search(r'\bQL\b', line):
            restrictions.append('QL')
        if re.search(r'\bDL\b', line):
            restrictions.append('DL')
        if re.search(r'\bMME\b', line):
            restrictions.append('MME')
        if re.search(r'\d+D', line):  # Days restriction like "7D"
            days_match = re.search(r'(\d+)D', line)
            if days_match:
                restrictions.append(f"{days_match.group(1)} day limit")
                
        info['restrictions'] = ', '.join(restrictions) if restrictions else 'None'

        # Extract dosage form from parentheses or context - use comprehensive forms list
        dosage_forms = self.comprehensive_forms_list if self.comprehensive_forms_list else [
            'oral concentrate', 'oral solution', 'oral tablet', 'immediate release', 'extended release',
            'external ointment', 'external patch', 'external solution', 'mouth/throat solution', 
            'external cream', 'tablet', 'capsule', 'injection', 'cream', 'ointment', 'solution', 
            'syrup', 'drops', 'pen', 'prefilled', 'concentrate', 'patch', 'viscous',
            'shampoo', 'topical shampoo', 'medicated shampoo'
        ]
        
        info['dosage_form'] = 'None'
        line_lower = line.lower()
        context_lower = context.lower()
        
        # Use comprehensive list with smart matching
        for form in sorted(dosage_forms, key=len, reverse=True):  # Check longer forms first
            if form in line_lower or form in context_lower:
                # Use master list to standardize the form
                standardized_form = MedicineFormsMaster.find_best_match(form)
                info['dosage_form'] = standardized_form.title()
                break

        # Extract strength from patterns like "50MG", "5%", "2.5-325MG"
        strength_match = re.search(r'(\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?)\s*(mg|mcg|g|ml|%)', line, re.IGNORECASE)
        if strength_match:
            info['strength'] = strength_match.group(0).upper()
        else:
            info['strength'] = 'None'
        
        return info

    def _extract_medicine_forms_enhanced(self, text: str, use_comprehensive_list: bool = True) -> List[str]:
        """
        Enhanced medicine form extraction using both dynamic detection and comprehensive master list.
        
        Args:
            text: Text to extract medicine forms from
            use_comprehensive_list: If True, use the comprehensive master list for detection
            
        Returns:
            List of detected medicine forms
        """
        found_forms = []
        
        if use_comprehensive_list:
            # Use comprehensive master list for reliable detection
            found_forms = MedicineFormsMaster.extract_forms_from_text(text)
            
            # If comprehensive list finds forms, prioritize those
            if found_forms:
                print(f"🎯 Found {len(found_forms)} medicine forms using comprehensive list: {found_forms[:5]}...")
                return found_forms
        
        # Fallback to dynamic extraction if comprehensive list doesn't find anything
        # or if explicitly requested to use dynamic extraction only
        print("🔍 Using dynamic medicine form extraction...")
        
        # Enhanced patterns that include the comprehensive list patterns
        enhanced_patterns = [
            # From master list - basic forms
            r'\b(tablet|capsule|pill|caplet|lozenge|wafer)s?\b',
            r'\b(solution|liquid|syrup|elixir|suspension|emulsion)s?\b',
            r'\b(injection|infusion|vaccine|serum)s?\b',
            r'\b(cream|ointment|gel|lotion|paste|foam|shampoo)s?\b',
            r'\b(patch|disc|film|strip|bandage)s?\b',
            r'\b(spray|mist|aerosol|inhaler|nebulizer)s?\b',
            r'\b(drops|oil|tincture|extract)s?\b',
            r'\b(powder|granules|pellets)s?\b',
            r'\b(suppository|enema|douche)s?\b',
            r'\b(implant|device|ring|coil)s?\b',
            
            # Compound forms with routes
            r'\b(oral\s+(?:tablet|capsule|solution|suspension|concentrate|powder|granules|film|strip|drops|syrup|elixir))s?\b',
            r'\b(chewable|dispersible|effervescent|sublingual|buccal|orally\s+disintegrating)\s+tablet\b',
            r'\b(mouth\s+rinse|mouthwash|throat\s+solution)\b',
            
            r'\b(topical|external)\s+(?:cream|ointment|gel|lotion|solution|spray|foam|patch|shampoo)s?\b',
            r'\b(dermal|skin)\s+patch\b',
            
            r'\b(subcutaneous|intramuscular|intravenous|intradermal|intrathecal|epidural|intraarticular|intravitreal)\s+injection\b',
            r'\b(prefilled\s+syringe|pen\s+injector|auto-injector)\b',
            r'\b(cartridge|vial|ampoule|infusion\s+bag)\b',
            
            r'\b(metered\s+dose\s+inhaler|dry\s+powder\s+inhaler|nebulizer\s+solution)\b',
            r'\b(inhalation\s+(?:aerosol|powder|solution))\b',
            r'\b(breath\s+activated|diskus|turbuhaler|rotahaler)\b',
            
            r'\b(nasal\s+(?:spray|drops|gel|ointment|solution|powder))\b',
            r'\b(eye\s+(?:drops|ointment|gel|solution)|ophthalmic\s+(?:drops|ointment|gel|solution|suspension))\b',
            r'\b(ear\s+(?:drops|solution|suspension)|otic\s+(?:drops|solution|suspension))\b',
            
            r'\b(rectal\s+(?:suppository|cream|ointment|solution|foam))\b',
            r'\b(vaginal\s+(?:suppository|cream|gel|tablet|ring|foam|solution|douche))\b',
            
            # Release mechanisms
            r'\b(immediate|extended|sustained|delayed|controlled|modified)\s+release\b',
            r'\b(enteric|film|sugar)\s+coated\b',
            
            # Special formulations
            r'\b(liposomal|microsphere|nanoparticle|emulsion|complex|conjugate|prodrug|biosimilar)\b',
            
            # Generic descriptors
            # r'\b(various|multiple|all\s+forms|different\s+strengths|assorted|mixed|unspecified)\b'
        ]
        
        text_lower = text.lower()
        
        # Search for each enhanced pattern
        for pattern in enhanced_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle grouped matches
                    for submatch in match:
                        if submatch:
                            form_name = submatch.strip()
                            form_name = re.sub(r'\s+', ' ', form_name)
                            if form_name and form_name not in found_forms:
                                found_forms.append(form_name)
                else:
                    form_name = match.strip()
                    form_name = re.sub(r'\s+', ' ', form_name)
                    if form_name and form_name not in found_forms:
                        found_forms.append(form_name)
        
        # Also search in parentheses with enhanced patterns
        parentheses_pattern = r'\([^)]*?(tablet|capsule|injection|cream|ointment|solution|syrup|drops|gel|spray|inhaler|patch|suppository|lotion|foam|powder|liquid|concentrate|suspension|release|oral|topical|external|nasal|eye|ear|rectal|vaginal|shampoo)[^)]*?\)'
        parentheses_matches = re.findall(parentheses_pattern, text_lower, re.IGNORECASE)
        
        for match in parentheses_matches:
            form_name = match.strip()
            if form_name and form_name not in found_forms:
                found_forms.append(form_name)
        
        # Use master list to standardize and validate found forms
        standardized_forms = []
        for form in found_forms:
            standardized_form = MedicineFormsMaster.find_best_match(form)
            if standardized_form and standardized_form not in standardized_forms:
                standardized_forms.append(standardized_form)
        
        print(f"🔍 Dynamic extraction found {len(standardized_forms)} medicine forms: {standardized_forms[:5]}...")
        return standardized_forms

    def get_comprehensive_medicine_forms(self, pdf_path: str = None, text: str = None, 
                                       use_comprehensive_list: bool = True) -> List[str]:
        """
        Get medicine forms using the comprehensive approach:
        1. Use comprehensive master list (recommended)
        2. Fallback to enhanced dynamic extraction
        3. Cache results for performance
        
        Args:
            pdf_path: Path to PDF file (optional)
            text: Direct text input (optional)
            use_comprehensive_list: Whether to use the comprehensive master list
            
        Returns:
            List of medicine forms
        """
        cache_key = None
        
        # Check cache if we have a PDF path
        if pdf_path:
            pdf_path = os.path.abspath(pdf_path)
            cache_key = f"comprehensive_{pdf_path}"
            
            if cache_key in self.dosage_forms_cache:
                print(f"Using cached comprehensive medicine forms for {os.path.basename(pdf_path)}")
                return self.dosage_forms_cache[cache_key]
        
        # Extract text if we have a PDF path but no text
        if pdf_path and not text:
            print(f"Extracting comprehensive medicine forms from {os.path.basename(pdf_path)}...")
            text = self._extract_pdf_text(pdf_path)
        
        if not text:
            print("No text available for medicine form extraction")
            return MedicineFormsMaster.get_all_forms()[:20]  # Return top 20 common forms as fallback
        
        # Use enhanced extraction method
        found_forms = self._extract_medicine_forms_enhanced(text, use_comprehensive_list)
        
        if not found_forms:
            print("No medicine forms found, using fallback from comprehensive list")
            # Return common forms from comprehensive list as fallback
            fallback_forms = [
                'tablet', 'capsule', 'solution', 'injection', 'cream', 
                'ointment', 'gel', 'patch', 'syrup', 'powder',
                'oral tablet', 'oral solution', 'topical cream', 'eye drops'
            ]
            found_forms = fallback_forms
        
        # Cache the results if we have a cache key
        if cache_key:
            self.dosage_forms_cache[cache_key] = found_forms
            print(f"Cached {len(found_forms)} comprehensive medicine forms for future use")
        
        return found_forms

    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text and tables from PDF document using pdfplumber."""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            row_text = ' | '.join(str(cell) for cell in row if cell)
                            if row_text.strip():
                                text += row_text + "\n"

            if text.strip():
                logger.info(f"Successfully extracted text and tables from {pdf_path} using pdfplumber")
                return text
            else:
                logger.warning(f"pdfplumber extracted no content from {pdf_path}. Trying PyPDF2.")

        except Exception as e:
            logger.error(f"pdfplumber failed for {pdf_path}, trying PyPDF2: {e}")

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

                if text.strip():
                    logger.info(f"Successfully extracted text from {pdf_path} using PyPDF2")
                    return text
                else:
                    logger.error(f"Both PDF readers failed to extract any text from {pdf_path}.")
                    raise ValueError("No text could be extracted from PDF")

        except Exception as e2:
            logger.error(f"Both PDF readers failed for {pdf_path}: {e2}")
            raise ValueError("PDF processing failed completely")

    def _extract_txt_text(self, txt_path: str) -> str:
        """Extract text from TXT document."""
        try:
            encodings = ['utf-8', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    with open(txt_path, 'r', encoding=encoding) as file:
                        return file.read()
                except UnicodeDecodeError:
                    continue
            raise ValueError("Could not decode text file with any encoding")
        except Exception as e:
            logger.error(f"Error extracting TXT text: {str(e)}")
            return ""

    def _process_csv_formulary(self, csv_path: str) -> List[Document]:
        """Process CSV formulary file."""
        try:
            parsing_strategies = [
                {'sep': ',', 'encoding': 'utf-8'},
                {'sep': '\t', 'encoding': 'utf-8'},
                {'sep': '|', 'encoding': 'utf-8'},
                {'sep': ',', 'encoding': 'latin-1'},
                {'sep': ';', 'encoding': 'utf-8'},
            ]

            df = None
            for strategy in parsing_strategies:
                try:
                    df = pd.read_csv(csv_path, **strategy)
                    if len(df.columns) > 1:
                        break
                except:
                    continue

            if df is None:
                raise ValueError("Could not parse CSV file")

            documents = []
            file_name = Path(csv_path).name

            for idx, row in df.iterrows():
                entry = self._parse_csv_row_to_drug_entry(row)
                if entry:
                    content = self._create_drug_content_from_entry(entry)
                    doc = Document(
                        page_content=content,
                        metadata={
                            'source_document': file_name,
                            'drug_name': entry.get('drug_name', ''),
                            'medicine_name': entry.get('drug_name', ''),  # Explicit medicine name field
                            'generic_name': entry.get('generic_name', ''),
                            'active_ingredient': entry.get('active_ingredient', ''),
                            'tier': entry.get('tier', ''),
                            'restrictions': entry.get('restrictions', ''),
                            'dosage_form': entry.get('dosage_form', ''),
                            'medicine_form': entry.get('medicine_form', entry.get('dosage_form', '')),  # Explicit medicine form field
                            'strength': entry.get('strength', ''),
                            'entry_type': 'formulary_drug',
                            'row_id': idx
                        }
                    )
                    documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"Error processing CSV formulary: {str(e)}")
            return []

    def _parse_csv_row_to_drug_entry(self, row: pd.Series) -> Dict[str, Any]:
        """Parse a CSV row into a standardized drug entry."""
        column_mappings = {
            'drug_name': ['Drug Name', 'drug_name', 'name', 'medication', 'brand_name'],
            'generic_name': ['Generic Name', 'generic_name', 'generic', 'active_ingredient'],
            'tier': ['Tier', 'tier', 'formulary_tier', 'cost_tier'],
            'restrictions': ['Restrictions', 'restrictions', 'coverage_restrictions', 'limits'],
            'dosage_form': ['Dosage Form', 'dosage_form', 'form', 'formulation'],
            'strength': ['Strength', 'strength', 'dose', 'dosage']
        }

        entry = {}
        row_dict = row.to_dict()

        for field, possible_columns in column_mappings.items():
            value = ''
            for col in possible_columns:
                if col in row_dict and pd.notna(row_dict[col]):
                    value = str(row_dict[col]).strip()
                    break
            entry[field] = value

        if not entry.get('drug_name') and not entry.get('generic_name'):
            return None

        entry['active_ingredient'] = entry.get('generic_name') or entry.get('drug_name')
        entry['medicine_form'] = entry.get('dosage_form', 'Unknown')  # Use 'Unknown' instead of 'Tablet' as default

        # USE PYDANTIC VALIDATION: Clean the CSV data to fix "same", "unknown" issues
        validated_entry = self._validate_medicine_with_pydantic(entry)
        
        return validated_entry

    def _create_drug_content_from_entry(self, entry: Dict[str, Any]) -> str:
        """Create optimized content for drug embeddings."""
        # Primary drug information for embeddings
        primary_content = []
        
        # Drug names (most important for search)
        if entry.get('drug_name'):
            primary_content.append(f"Drug: {entry['drug_name']}")
        if entry.get('generic_name') and entry.get('generic_name') != entry.get('drug_name'):
            primary_content.append(f"Generic: {entry['generic_name']}")
        if entry.get('active_ingredient'):
            primary_content.append(f"Active ingredient: {entry['active_ingredient']}")
            
        # Therapeutic information
        if entry.get('therapeutic_class'):
            primary_content.append(f"Class: {entry['therapeutic_class']}")
            
        # Formulary details - make medicine form more prominent
        formulary_info = []
        if entry.get('tier'):
            formulary_info.append(f"Tier: {entry['tier']}")
        if entry.get('restrictions') and entry.get('restrictions') != 'None':
            formulary_info.append(f"Restrictions: {entry['restrictions']}")
        
        # Prioritize medicine_form over dosage_form for better visibility
        medicine_form = entry.get('medicine_form') or entry.get('dosage_form')
        if medicine_form and medicine_form.lower() not in ['none', 'unknown', 'same', 'unclear']:
            formulary_info.append(f"Form: {medicine_form}")
            primary_content.append(f"Medicine Form: {medicine_form}")  # Add to primary content for better embedding
        else:
            # Try to infer form from drug name if still missing
            drug_name = entry.get('drug_name', '')
            if drug_name:
                extracted_info = self._extract_drug_name_and_form(drug_name)
                inferred_form = extracted_info.get('medicine_form', 'Tablet')
                formulary_info.append(f"Form: {inferred_form}")
                primary_content.append(f"Medicine Form: {inferred_form}")
            else:
                formulary_info.append(f"Form: Tablet")  # Default form
                primary_content.append(f"Medicine Form: Tablet")
        
        if entry.get('strength') and entry.get('strength').lower() not in ['none', 'unknown', 'same', 'unclear']:
            formulary_info.append(f"Strength: {entry['strength']}")
            
        # Combine all information
        content_parts = primary_content + formulary_info
        
        # Add searchable variations for better embedding matching - CLEANED
        searchable_terms = []
        if entry.get('drug_name'):
            drug_name_clean = entry['drug_name'].lower()
            if drug_name_clean not in ['same', 'unknown', 'unclear']:
                searchable_terms.append(drug_name_clean)
        
        if entry.get('generic_name'):
            generic_name_clean = entry['generic_name'].lower()
            if generic_name_clean not in ['same', 'unknown', 'unclear'] and generic_name_clean != entry.get('drug_name', '').lower():
                searchable_terms.append(generic_name_clean)
        
        if entry.get('active_ingredient'):
            active_ingredient_clean = entry['active_ingredient'].lower()
            if active_ingredient_clean not in ['same', 'unknown', 'unclear']:
                searchable_terms.append(active_ingredient_clean)
        
        # Add medicine form to searchable terms for better matching
        if medicine_form:
            searchable_terms.append(medicine_form.lower())
            
        # Create final content optimized for semantic search
        main_content = " | ".join(content_parts)
        search_content = f"Alternative names: {', '.join(set(searchable_terms))}"
        
        return f"{main_content} | {search_content}"

    def _update_drug_database(self, drug_entries: List[Dict[str, Any]], source_name: str):
        """Update the internal drug database for alternative finding with validation."""
        valid_entries = 0
        filtered_entries = 0
        
        for entry in drug_entries:
            # Validate the entry before adding to database
            if not self._is_valid_medicine_entry(entry):
                filtered_entries += 1
                continue
                
            active_ingredient = entry.get('active_ingredient', '').lower().strip()
            if active_ingredient:
                if active_ingredient not in self.drug_database:
                    self.drug_database[active_ingredient] = []
                entry['source_document'] = source_name
                self.drug_database[active_ingredient].append(entry)
                valid_entries += 1
        
        if filtered_entries > 0:
            print(f"🧹 Database cleanup: Added {valid_entries} valid entries, filtered out {filtered_entries} invalid entries from {source_name}")
        else:
            print(f"✅ Added {valid_entries} valid entries to database from {source_name}")
    
    def cleanup_database_invalid_entries(self):
        """Clean up the database by removing invalid drug entries."""
        print("🧹 Starting database cleanup to remove invalid entries...")
        
        total_before = 0
        total_after = 0
        removed_entries = []
        
        # Count total entries before cleanup
        for ingredient, drugs in self.drug_database.items():
            total_before += len(drugs)
        
        # Clean each ingredient category
        for ingredient, drugs in list(self.drug_database.items()):
            valid_drugs = []
            
            for drug in drugs:
                if self._is_valid_medicine_entry(drug):
                    valid_drugs.append(drug)
                else:
                    removed_entries.append(drug.get('drug_name', 'Unknown'))
            
            if valid_drugs:
                self.drug_database[ingredient] = valid_drugs
                total_after += len(valid_drugs)
            else:
                # Remove ingredient category if no valid drugs remain
                del self.drug_database[ingredient]
        
        # Update the drug names cache after cleanup
        self._update_drug_names_cache()
        
        print(f"🧹 Database cleanup complete:")
        print(f"   - Before: {total_before} entries")
        print(f"   - After: {total_after} entries")
        print(f"   - Removed: {total_before - total_after} invalid entries")
        
        if removed_entries:
            print(f"   - Removed entries: {', '.join(removed_entries[:10])}{'...' if len(removed_entries) > 10 else ''}")
        
        return {
            'total_before': total_before,
            'total_after': total_after,
            'removed_count': total_before - total_after,
            'removed_entries': removed_entries
        }

    def create_vectorstore(self, documents: List[Document]) -> None:
        """Create and populate the ChromaDB vector store optimized for drug entries."""
        if not documents:
            raise ValueError("No documents provided for vectorization")

        # Filter documents to only include actual drug entries (not text chunks)
        drug_documents = [doc for doc in documents if doc.metadata.get('drug_name')]
        
        if not drug_documents:
            logger.warning("No drug documents found, using all documents")
            drug_documents = documents
        
        logger.info(f"Creating embeddings for {len(drug_documents)} drug entries")

        # Use minimal splitting since each document is already a complete drug entry
        split_docs = self.text_splitter.split_documents(drug_documents)
        logger.info(f"Split into {len(split_docs)} chunks for embedding")

        # Log sample content for debugging
        if split_docs:
            logger.info(f"Sample drug content for embedding: {split_docs[0].page_content[:200]}...")

        self.vectorstore = Chroma.from_documents(
            documents=split_docs,
            embedding=self.embeddings,
            persist_directory=self.chroma_persist_directory
        )

        # Configure retriever to get more relevant drug matches
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}  # Get more alternatives
        )

        # Set up hybrid retriever combining semantic + BM25 search
        self.hybrid_retriever = self._setup_hybrid_retriever(split_docs)

        logger.info(f"✅ Vector store created with {len(split_docs)} drug embeddings")
        
        # 🧹 AUTOMATIC CLEANUP: Run database cleanup after creation to remove invalid entries
        if self.auto_cleanup:
            try:
                logger.info("🧹 Running automatic database cleanup to remove invalid entries...")
                cleanup_result = self.cleanup_database_invalid_entries()
                cleanup_count = cleanup_result.get('removed_count', 0)
                if cleanup_count > 0:
                    logger.info(f"✅ Automatic cleanup completed: removed {cleanup_count} invalid entries")
                else:
                    logger.info("✅ Automatic cleanup completed: no invalid entries found")
            except Exception as e:
                logger.warning(f"⚠️ Automatic cleanup failed (continuing anyway): {e}")
                # Don't fail the entire process if cleanup fails
        else:
            logger.info("ℹ️ Automatic cleanup is disabled (auto_cleanup=False)")

    def _setup_hybrid_retriever(self, documents: List[Document]):
        """Set up hybrid retriever combining BM25 (lexical) and semantic search."""
        if not BM25_AVAILABLE:
            logger.warning("BM25 not available, using semantic search only")
            return self.retriever
        
        try:
            # Create BM25 retriever for lexical matching (good for exact brand/generic names)
            bm25_retriever = BM25Retriever.from_documents(documents)
            bm25_retriever.k = 5  # Get fewer BM25 results to balance with semantic
            
            # Create ensemble retriever combining both
            ensemble_retriever = EnsembleRetriever(
                retrievers=[self.retriever, bm25_retriever],
                weights=[0.7, 0.3]  # Favor semantic search but include lexical
            )
            
            logger.info("✅ Hybrid retriever (semantic + BM25) configured")
            return ensemble_retriever
            
        except Exception as e:
            logger.warning(f"Failed to setup hybrid retriever: {e}, using semantic only")
            return self.retriever

    def vectorstore_exists(self) -> bool:
        """Check if a vector store already exists."""
        try:
            db_path = Path(self.chroma_persist_directory)
            # Check if the directory exists and has chroma database files
            if db_path.exists():
                chroma_files = list(db_path.glob("chroma.sqlite3")) or list(db_path.glob("*.sqlite3"))
                if chroma_files:
                    logger.info(f"✅ Found existing database at {db_path}")
                    return True
            logger.info(f"❌ No existing database found at {db_path}")
            return False
        except Exception as e:
            logger.warning(f"Error checking database existence: {str(e)}")
            return False

    def load_existing_vectorstore(self) -> bool:
        """Load existing ChromaDB vector store."""
        try:
            if not self.vectorstore_exists():
                return False
                
            logger.info("🔄 Loading existing vector store...")
            self.vectorstore = Chroma(
                persist_directory=self.chroma_persist_directory,
                embedding_function=self.embeddings
            )
            
            # Test the vectorstore locally without calling OpenAI API
            test_results = self.vectorstore.get(limit=1)
            if not test_results or not test_results.get('ids'):
                logger.warning("Existing database appears empty")
                return False
                
            self.retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 6}
            )
            
            # Set up hybrid retriever if possible
            try:
                # Get all documents for hybrid setup
                all_docs_data = self.vectorstore.get()
                if 'documents' in all_docs_data and 'metadatas' in all_docs_data:
                    # Reconstruct documents for BM25
                    documents = []
                    for i, (content, metadata) in enumerate(zip(all_docs_data['documents'], all_docs_data['metadatas'])):
                        if content and metadata:
                            doc = Document(page_content=content, metadata=metadata)
                            documents.append(doc)
                    
                    if documents:
                        self.hybrid_retriever = self._setup_hybrid_retriever(documents)
                    else:
                        self.hybrid_retriever = self.retriever
                else:
                    self.hybrid_retriever = self.retriever
            except Exception as e:
                logger.warning(f"Could not setup hybrid retriever for existing DB: {e}")
                self.hybrid_retriever = self.retriever
            
            # Load drug database from existing vectorstore metadata
            self._load_drug_database_from_vectorstore()
            
            logger.info(f"✅ Successfully loaded existing vector store with {len(test_results)} entries")
            
            # 🧹 AUTOMATIC CLEANUP: Run database cleanup after loading to remove invalid entries
            if self.auto_cleanup:
                try:
                    logger.info("🧹 Running automatic database cleanup after loading...")
                    cleanup_result = self.cleanup_database_invalid_entries()
                    cleanup_count = cleanup_result.get('removed_count', 0)
                    if cleanup_count > 0:
                        logger.info(f"✅ Automatic cleanup completed: removed {cleanup_count} invalid entries")
                    else:
                        logger.info("✅ Automatic cleanup completed: no invalid entries found")
                except Exception as e:
                    logger.warning(f"⚠️ Automatic cleanup failed (continuing anyway): {e}")
            else:
                logger.info("ℹ️ Automatic cleanup is disabled (auto_cleanup=False)")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error loading existing vector store: {str(e)}")
            return False

    def _load_drug_database_from_vectorstore(self):
        """Load drug database from existing vectorstore metadata."""
        try:
            # Get all documents from vectorstore to rebuild drug_database
            all_docs = self.vectorstore.get()
            
            if 'metadatas' in all_docs:
                for metadata in all_docs['metadatas']:
                    if metadata and 'active_ingredient' in metadata and ('drug_name' in metadata or 'medicine_name' in metadata):
                        # Prefer explicit medicine_name if present, fallback to drug_name
                        drug_name = metadata.get('medicine_name') or metadata.get('drug_name', '')
                        # Get medicine form, prefer explicit medicine_form field
                        medicine_form = metadata.get('medicine_form') or metadata.get('dosage_form', '')
                        
                        # Validate drug name before adding to database
                        if not self._is_valid_drug_name(drug_name):
                            #print(f"⚠️ DEBUG: Filtered out invalid drug name from metadata: '{drug_name}'")
                            continue
                        
                        active_ingredient = metadata['active_ingredient'].lower()
                        if active_ingredient not in self.drug_database:
                            self.drug_database[active_ingredient] = []
                        
                        drug_entry = {
                            'drug_name': drug_name,
                            'generic_name': metadata.get('generic_name', ''),
                            'active_ingredient': active_ingredient,
                            'therapeutic_class': metadata.get('therapeutic_class', ''),
                            'tier': metadata.get('tier', ''),
                            'restrictions': metadata.get('restrictions', ''),
                            'dosage_form': medicine_form,  # Use the preferred form field
                            'medicine_form': medicine_form,  # Add explicit medicine_form field
                            'strength': metadata.get('strength', ''),
                            'source_document': metadata.get('source_document', '')
                        }
                        
                        # Add all entries including duplicates for complete results
                        self.drug_database[active_ingredient].append(drug_entry)
            
            # Update cache
            self._update_drug_names_cache()
            
            total_drugs = sum(len(drugs) for drugs in self.drug_database.values())
            logger.info(f"📊 Loaded {total_drugs} drugs with {len(self.drug_database)} active ingredients from existing database")
            
            # Automatically clean up invalid entries after loading
            print("🧹 Running automatic database cleanup after loading...")
            cleanup_results = self.cleanup_database_invalid_entries()
            
            if cleanup_results['removed_count'] > 0:
                print(f"🧹 Cleanup completed: Removed {cleanup_results['removed_count']} invalid entries")
            else:
                print("✅ No invalid entries found - database is clean")
            
        except Exception as e:
            logger.warning(f"Could not load drug database from vectorstore: {str(e)}")

    def setup_rag_chain(self) -> None:
        """Set up the RAG chain for question answering."""
        if not self.retriever:
            raise ValueError("Retriever not initialized. Call create_vectorstore or load_existing_vectorstore first.")

        self.rag_chain = (
            {"context": self.retriever | self._format_docs, "question": RunnablePassthrough()}
            | self.prompt_template
            | self.llm
            | StrOutputParser()
        )

        logger.info("RAG chain configured")

    def _format_docs(self, docs: List[Document]) -> str:
        """Format retrieved documents for the prompt."""
        return "\n\n".join(doc.page_content for doc in docs)

    def query(self, question: str, use_hybrid: bool = True) -> Dict[str, Any]:
        """Query the RAG system for formulary drug information with optional hybrid search."""
        if not self.rag_chain:
            raise ValueError("RAG chain not set up. Call setup_rag_chain first.")

        try:
            # Choose retriever based on availability and preference
            active_retriever = self.hybrid_retriever if (use_hybrid and self.hybrid_retriever) else self.retriever
            
            retrieved_docs = active_retriever.invoke(question)
            # print(f"🔍 DEBUG: Retrieved {len(retrieved_docs)} docs using {'hybrid' if use_hybrid and self.hybrid_retriever else 'semantic'} search")
            
            # 🔍 CONSOLE LOG: Log the RAG query to OpenAI
            # print(f"\n🤖 OPENAI RAG QUERY for: '{question}'")
            # print(f"📝 Context being sent to OpenAI:")
            # print(f"{'='*80}")
            formatted_context = self._format_docs(retrieved_docs)
            # print(formatted_context[:1000] + "..." if len(formatted_context) > 1000 else formatted_context)
            # print(f"{'='*80}")
            
            answer = self.rag_chain.invoke(question)
            
            # # 🔍 CONSOLE LOG: Log OpenAI's RAG response
            # print(f"\n💬 OPENAI RAG RESPONSE:")
            # print(f"{'='*80}")
            # print(answer)
            # print(f"{'='*80}")
        except Exception as e:
            logger.error(f"Error during RAG query: {str(e)}")
            return {
                "answer": f"Error during search: {str(e)}",
                "source_documents": [],
                "num_sources": 0
            }

        return {
            "answer": answer,
            "source_documents": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in retrieved_docs
            ],
            "num_sources": len(retrieved_docs)
        }

    def get_generic_and_therapeutic_equivalents(self, drug_name: str, full_query: str = None) -> Dict[str, Any]:
        """Get generic name and therapeutic equivalents using comprehensive AI analysis with parallel processing.
        If full_query is provided (containing patient context), the AI will consider it for smarter suggestions.
        """
        
        # If AI enhancement is disabled, return basic info
        if not self.enable_ai_enhancement:
            result = {
                "generic_name": drug_name.lower(),
                "active_ingredient": drug_name.lower(),
                "therapeutic_class": "Unknown",
                "therapeutic_equivalents": [],
                "indication": "Unknown",
                "mechanism": "Unknown"
            }
            return result
        
        # Check cache first for therapeutic info
        cache_key = self._get_cache_key('therapeutic_info', drug_name.lower())
        cached_result = self._get_from_cache(self.search_cache, cache_key)
        if cached_result is not None:
            return cached_result
        
        # Clean the drug name first using number-based splitting to ensure accurate therapeutic analysis
        # Extract just the drug name up to the first number (like "Galantamine" from "Galantamine 100 MG oral capsule")
        base_drug_name = re.split(r'\s*\d', drug_name)[0].strip() if drug_name else drug_name
        cleaned_drug_name = base_drug_name
        #print(f"🧹 Drug name cleaning: '{drug_name}' → '{cleaned_drug_name}'")

        # --- NEW: FAST PATH LOCAL LOOKUP ---
        try:
            from backend.services.safety_model_service import safety_service
            local_info = safety_service.get_drug_info(cleaned_drug_name)
            if local_info:
                #print(f"⚡ FAST PATH: Local ML info found for '{cleaned_drug_name}'")
                result = {
                    "generic_name": local_info.get('generic_name', cleaned_drug_name.lower()),
                    "active_ingredient": local_info.get('generic_name', cleaned_drug_name.lower()),
                    "therapeutic_class": local_info.get('drug_classes', 'Unknown'),
                    "therapeutic_equivalents": [], # Will be populated by check_alternatives_in_formulary
                    "indication": local_info.get('medical_condition', 'Unknown'),
                    "mechanism": "Local ML Analysis"
                }
                # Cache and return immediately
                self._set_cache(self.search_cache, cache_key, result)
                return result
        except Exception as e:
            #print(f"⚠️ Local lookup failed: {e}")
            pass
        # --- END FAST PATH ---
        
        try:
            # OPTIMIZATION: Run both API calls in parallel to reduce completion API latency
            def get_generic_name():
                direct_prompt = f"""
What is the generic name (active ingredient) for the medication "{drug_name}"?

Please respond with ONLY the generic name, nothing else.

Examples:
- Zepbound -> Tirzepatide
- Ozempic -> Semaglutide  
- Wegovy -> Semaglutide
- Mounjaro -> Tirzepatide
- Lipitor -> Atorvastatin

Generic name for {drug_name}:"""
                try:
                    # Use direct OpenAI client to bypass LangChain/OpenTelemetry issues
                    import openai
                    import os
                    
                    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": direct_prompt}],
                        temperature=0,
                        max_tokens=100
                    )
                    
                    return response.choices[0].message.content.strip()
                    
                except Exception as e:
                    print(f"🚨 Error in get_generic_name: {e}")
                    # Return a fallback response
                    return drug_name

            def get_combined_info():
                """Get both generic name and therapeutic class in a single API call for efficiency."""
                input_query = full_query if full_query else cleaned_drug_name
                combined_prompt = f"""
For the medication "{input_query}", provide:
1. Generic name (active ingredient)
2. Therapeutic class
3. List 5 therapeutic equivalents (other drugs in the same class or with similar indication)

IMPORTANT: If patient context is provided (e.g. 'for a patient with...'), please ensure the therapeutic equivalents are generally considered safer for that specific context if possible.

Please respond in this exact format:
Generic: [generic name]
Class: [therapeutic class]
Equivalents: [drug1], [drug2], [drug3], [drug4], [drug5]

Examples:
Generic: Tirzepatide
Class: GLP-1/GIP receptor agonist
Equivalents: Semaglutide, Liraglutide, Exenatide, Dulaglutide, Albiglutide

For {input_query}:"""
                try:
                    # Use direct OpenAI client to bypass LangChain/OpenTelemetry issues
                    import openai
                    import os
                    
                    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": combined_prompt}],
                        temperature=0,
                        max_tokens=200
                    )
                    
                    return response.choices[0].message.content.strip()
                    
                except Exception as e:
                    print(f"🚨 Error in get_combined_info: {e}")
                    # Return a fallback response
                    return f"Generic: {cleaned_drug_name}\nClass: Unknown"
            
            # Use combined approach for better efficiency
            # print(f"\n🤖 OPENAI THERAPEUTIC INFO REQUEST for '{drug_name}':")
            # print(f"📝 Asking OpenAI for generic name and therapeutic class...")
            
            # CONSIDERING PERFORMANCE: ONLY use combined info, remove fallback logic unless critical failure
            combined_response = get_combined_info()
            
            # Parse the combined response
            generic_name = drug_name  # fallback
            therapeutic_class = "Unknown"  # fallback
            
            lines = combined_response.split('\n')
            ai_equivalents = []
            for line in lines:
                line = line.strip()
                if line.startswith('Generic:'):
                    generic_name = line.replace('Generic:', '').strip()
                elif line.startswith('Class:'):
                    therapeutic_class = line.replace('Class:', '').strip()
                elif line.startswith('Equivalents:'):
                    equivs = line.replace('Equivalents:', '').strip()
                    if equivs:
                        ai_equivalents = [e.strip() for e in equivs.split(',') if e.strip()]
            
            # Validate generic name - if OpenAI failed or gave junk, only then use the fallback
            if not generic_name or len(generic_name) < 3 or generic_name.lower() == "unknown":
                generic_name = get_generic_name()
            
            if not generic_name or len(generic_name) < 3:
                generic_name = drug_name  # Ultimate fallback
            
            therapeutic_equivalents = ai_equivalents.copy()
            if therapeutic_class and therapeutic_class != "Unknown":
                db_equivalents = self._get_therapeutic_equivalents_from_class(therapeutic_class)
                # Merge and remove duplicates
                for eq in db_equivalents:
                    if eq.lower() not in [a.lower() for a in therapeutic_equivalents]:
                        therapeutic_equivalents.append(eq)

            result = {
                "generic_name": generic_name,
                "active_ingredient": generic_name.lower(),
                "therapeutic_class": therapeutic_class,
                "therapeutic_equivalents": therapeutic_equivalents,
                "indication": "As determined by therapeutic class",
                "mechanism": therapeutic_class
            }
            
            # Cache the result
            self._set_cache(self.search_cache, cache_key, result)
            return result
            
        except Exception as e:
            print(f"⚠️ Error in therapeutic info generation: {e}")
            # Use fallback
            result = {
                "generic_name": drug_name,
                "active_ingredient": drug_name.lower(),
                "therapeutic_class": "Unknown",
                "therapeutic_equivalents": [],
                "indication": "Unknown",
                "mechanism": "Unknown"
            }
            return result

    def _get_therapeutic_equivalents_from_class(self, therapeutic_class: str) -> List[str]:
        """Get therapeutic equivalents based on drug class using AI analysis."""
        if not therapeutic_class or therapeutic_class == "Unknown":
            return []
       
        try:
            # Use AI to find therapeutic equivalents based on class - with stricter criteria
            equivalents_prompt = f"""
List 2-3 medications that have the SAME active ingredient or IDENTICAL mechanism of action as drugs in the therapeutic class: {therapeutic_class}
 
STRICT CRITERIA:
- Must have same active ingredient OR identical mechanism of action
- Must be clinically interchangeable alternatives
- Do NOT include drugs that are merely in the same broad category
- Do NOT include drugs with different mechanisms of action
 
Provide ONLY the exact drug names (generic names preferred), one per line, no explanations.
 
Example format:
Drug1
Drug2
 
True therapeutic equivalents for {therapeutic_class}:"""
 
            # Use direct OpenAI client to bypass LangChain/OpenTelemetry issues
            try:
                import openai
                import os
                
                client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                llm_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": equivalents_prompt.format(therapeutic_class=therapeutic_class)}],
                    temperature=0,
                    max_tokens=200
                )
                
                response = llm_response.choices[0].message.content
                
            except Exception as e:
                print(f"🚨 Error in therapeutic equivalents generation: {e}")
                response = ""
           
            # Parse the response into a list with stricter filtering
            equivalents = []
            for line in response.strip().split('\n'):
                drug_name = line.strip().replace('-', '').replace('*', '').strip()
                if drug_name and len(drug_name) > 2 and not any(x in drug_name.lower() for x in ['unknown', 'various', 'same', 'identical']):
                    equivalents.append(drug_name)
           
            return equivalents[:3]  # Limit to 3 results for precision
           
        except Exception as e:
            logger.warning(f"Could not get therapeutic equivalents for {therapeutic_class}: {str(e)}")
            return []

    def check_alternatives_in_formulary(self, therapeutic_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check which therapeutic equivalents exist in the insurance formulary."""
        
        formulary_alternatives = []
        
        # Get the main active ingredient
        main_ingredient = therapeutic_info.get('active_ingredient', '').lower()
        generic_name = therapeutic_info.get('generic_name', '').lower()
        
        
        # 1. Check for exact matches of the main drug
        for ingredient, drugs in self.drug_database.items():
            if ingredient == main_ingredient or ingredient == generic_name:
                for drug in drugs:
                    drug_copy = drug.copy()
                    drug_copy['match_type'] = 'exact_ingredient'
                    drug_copy['similarity_score'] = 1.0
                    formulary_alternatives.append(drug_copy)
        
        # 2. Check therapeutic equivalents
        therapeutic_equivalents = therapeutic_info.get('therapeutic_equivalents', [])
        
        for equivalent in therapeutic_equivalents:
            equivalent_lower = equivalent.lower().strip()
            # Search by ingredient name
            if equivalent_lower in self.drug_database:

                for drug in self.drug_database[equivalent_lower]:
                    drug_copy = drug.copy()
                    drug_copy['match_type'] = 'therapeutic_equivalent'
                    drug_copy['similarity_score'] = 0.7
                    formulary_alternatives.append(drug_copy)
            
            # Search by drug name similarity
            for ingredient, drugs in self.drug_database.items():
                for drug in drugs:
                    drug_name = drug.get('drug_name', '').lower()
                    generic_name = drug.get('generic_name', '').lower()
                    
                    if (equivalent_lower in drug_name or equivalent_lower in generic_name or
                        drug_name in equivalent_lower or generic_name in equivalent_lower):

                        drug_copy = drug.copy()
                        drug_copy['match_type'] = 'partial_match'
                        drug_copy['similarity_score'] = 0.6
                        formulary_alternatives.append(drug_copy)
        
        # Remove duplicates based on drug name and validate drug names
        seen_drugs = set()
        unique_alternatives = []
        for alt in formulary_alternatives:
            # Validate drug names before adding to results
            drug_name = alt.get('drug_name', '')
            generic_name = alt.get('generic_name', '')
            
            # Check if the drug names are valid
            if not self._is_valid_drug_name(drug_name):
                continue
                
            # Removed: medicine form "none" check - let LLM classification handle it instead
            
            if generic_name and not self._is_valid_drug_name(generic_name):

                # Keep the entry but clear the invalid generic name
                alt['generic_name'] = drug_name
            
            # Normalize drug names to handle salt forms (e.g., "Metformin" vs "Metformin HCl")
            normalized_drug_name = self._normalize_drug_name_for_comparison(drug_name)
            normalized_generic_name = self._normalize_drug_name_for_comparison(alt.get('generic_name', ''))
            medicine_form = alt.get('medicine_form') or alt.get('dosage_form', 'Unknown')
            
            # Create unique key that includes medicine form to allow different forms of same drug
            drug_key = (normalized_drug_name, normalized_generic_name, medicine_form)
            if drug_key not in seen_drugs:
                seen_drugs.add(drug_key)
                unique_alternatives.append(alt)
        
        #print(f"📊 DEBUG: Found {len(unique_alternatives)} unique and validated alternatives in formulary")
        
        # 3. NEW: Search for drugs where our search terms appear in their alternative names
        # Try both vector-based and direct search methods in parallel with optimization
        alternative_names_matches = []
        
        # Check cache for alternative names search
        alt_cache_key = self._get_cache_key('alt_search', therapeutic_info)
        cached_alt_results = self._get_from_cache(self.search_cache, alt_cache_key)
        
        if cached_alt_results is not None:
            alternative_names_matches = cached_alt_results
        else:
            # Initialize match lists to avoid UnboundLocalError
            vector_matches = []
            direct_matches = []
            
            # Use ThreadPoolExecutor with timeout and early termination
            with ThreadPoolExecutor(max_workers=min(2, self.max_workers)) as executor:
                # Submit both search methods for parallel execution
                vector_future = executor.submit(self._search_by_alternative_names_comparison, therapeutic_info)
                direct_future = executor.submit(self._search_by_alternative_names_direct, therapeutic_info)
                
                # Collect results as they complete with timeout
                try:
                    for future in as_completed([vector_future, direct_future], timeout=30):
                        try:
                            if future == vector_future:
                                vector_matches = future.result()
                            elif future == direct_future:
                                direct_matches = future.result()
                        except Exception as e:
                            # logger.warning(f"Alternative search method failed: {str(e)}")
                            pass
                except Exception as timeout_e:
                    # logger.warning(f"Alternative search timeout: {str(timeout_e)}")
                    pass
            
            # Combine results
            alternative_names_matches.extend(vector_matches)
            
            # Merge direct matches, avoiding duplicates with vector matches
            for dm in direct_matches:
                dm_key = dm.get('drug_name', '').lower()
                if dm_key not in [vm.get('drug_name', '').lower() for vm in vector_matches]:
                    alternative_names_matches.append(dm)
            
            # Cache the combined results
            if alternative_names_matches:
                self._set_cache(self.search_cache, alt_cache_key, alternative_names_matches)
        
        #print(f"🎯 DEBUG: Combined alternative names search returned {len(alternative_names_matches)} total matches")
        
        if alternative_names_matches:
            #print(f"📋 DEBUG: Alternative names matches summary:")
            for i, match in enumerate(alternative_names_matches, 1):
                match_type = match.get('match_type', 'unknown')
                matched_term = match.get('matched_term', 'N/A')
                #print(f"   {i}. {match['drug_name']} (generic: {match.get('generic_name', 'N/A')}) - {match_type} via '{matched_term}'")
        
        # Merge alternative names matches with existing results
        added_count = 0
        for alt_match in alternative_names_matches:
            # Normalize drug names to handle salt forms (e.g., "Metformin" vs "Metformin HCl")
            normalized_drug_name = self._normalize_drug_name_for_comparison(alt_match.get('drug_name', ''))
            normalized_generic_name = self._normalize_drug_name_for_comparison(alt_match.get('generic_name', ''))
            medicine_form = alt_match.get('medicine_form') or alt_match.get('dosage_form', 'Unknown')
            
            # Create unique key that includes medicine form to allow different forms of same drug
            drug_key = (normalized_drug_name, normalized_generic_name, medicine_form)
            if drug_key not in seen_drugs:
                seen_drugs.add(drug_key)
                unique_alternatives.append(alt_match)
                added_count += 1
        
        #print(f"✅ DEBUG: Added {added_count} new alternatives from alternative names search")
        #print(f"📊 DEBUG: Total {len(unique_alternatives)} unique alternatives after alternative names search")
        return unique_alternatives

    def _clean_drug_name_with_llm(self, raw_drug_name: str) -> str:
        """Use LLM to clean drug names and remove forms, dosages, and other details."""
        if not raw_drug_name or len(raw_drug_name.strip()) < 2:
            return raw_drug_name
        
        # Cache key for LLM drug name cleaning
        cache_key = self._get_cache_key('clean_drug_name', raw_drug_name.lower())
        cached_result = self._get_from_cache(self.search_cache, cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            cleaning_prompt = f"""
Extract ONLY the core drug/medicine name from the following text, removing all dosage forms, strengths, routes, and other details.

EXAMPLES:
- "erythromycin with ethanol topical gel" → "erythromycin"
- "metformin hcl extended release tablet" → "metformin"
- "ibuprofen 200mg oral capsule" → "ibuprofen"
- "tretinoin microspheres topical gel" → "tretinoin"
- "insulin glargine injection pen" → "insulin glargine"
- "atorvastatin calcium tablet" → "atorvastatin"
- "lisinopril oral solution" → "lisinopril"

RULES:
1. Keep only the active drug name
2. Remove dosage forms (tablet, capsule, gel, cream, solution, etc.)
3. Remove strengths (mg, mcg, %, ml, etc.)
4. Remove routes (oral, topical, injectable, etc.)
5. Remove additives (with ethanol, benzyl alcohol, etc.)
6. Keep salt forms if they're part of the drug name (like "metformin hcl")
7. Preserve brand names exactly as written

Input: "{raw_drug_name}"
Clean drug name:"""

            # invoke the text LLM with proper message format
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=cleaning_prompt)]
            response = self.llm_text.invoke(messages)

            # robustly extract text from whatever the LLM returned
            cleaned_text = None
            # 1) common LangChain Chat message object (AIMessage-like)
            if hasattr(response, "content"):
                cleaned_text = response.content
            # 1.5) Handle LegacyAPIResponse from OpenTelemetry
            elif hasattr(response, 'choices') and len(response.choices) > 0:
                cleaned_text = response.choices[0].message.content
            # 2) some LangChain chains return dict or list
            elif isinstance(response, dict):
                # try common keys
                for k in ("text", "content", "response", "answer"):
                    if k in response and isinstance(response[k], str):
                        cleaned_text = response[k]
                        break
                if cleaned_text is None:
                    cleaned_text = ' '.join([str(v) for v in response.values() if isinstance(v, str)])
            # 3) plain string
            elif isinstance(response, str):
                cleaned_text = response
            else:
                # fallback to str()
                cleaned_text = str(response)

            # sanitize the result: remove any prompt labels like "Clean drug name:" and quotes
            if cleaned_text is None:
                cleaned_text = ""
            # remove labels (case-insensitive)
            cleaned_text = re.sub(r'(?i)clean\s*drug\s*name\s*[:\-]?', '', cleaned_text).strip()
            # remove surrounding quotes
            cleaned_text = cleaned_text.strip().strip('"').strip("'").strip()

            # if the LLM returned multiple lines, take the first reasonable line
            if '\n' in cleaned_text:
                # keep the first non-empty short line
                for line in cleaned_text.splitlines():
                    line = line.strip()
                    if line:
                        cleaned_text = line
                        break

            # final basic validation
            cleaned_name = cleaned_text
            if not cleaned_name or len(cleaned_name) < 2 or cleaned_name.lower() in ['unknown', 'unclear', 'n/a', 'none']:
                # fallback to pattern-based extraction
                extraction_result = self._extract_drug_name_and_form_from_raw(raw_drug_name)
                cleaned_name = extraction_result.get('drug_name', raw_drug_name)

            # normalize spacing and capitalization but preserve multiword drug names as lowercase for matching consistency
            cleaned_name = cleaned_name.strip()
            # preserve common salt tokens (user rule #6). Do not force title() which may break all-caps acronyms
            # minimal normalization: collapse multiple spaces
            cleaned_name = re.sub(r'\s+', ' ', cleaned_name)

            # cache & return
            self._set_cache(self.search_cache, cache_key, cleaned_name)
            return cleaned_name

        except Exception as e:
            print(f"⚠️ LLM drug name cleaning failed for '{raw_drug_name}': {e}")
            extraction_result = self._extract_drug_name_and_form_from_raw(raw_drug_name)
            return extraction_result.get('drug_name', raw_drug_name)

    def _is_valid_medicine_entry(self, medicine: Dict[str, Any]) -> bool:
        """Validate that an entry represents a legitimate medicine using comprehensive checks."""
        drug_name = medicine.get('drug_name', '').strip()
        
        # Basic validation
        if not drug_name or len(drug_name) < 2:
            return False
        
        # CRITICAL: Check for the specific problematic entries mentioned by user
        problematic_drug_names = {
            'capitalized', 'lowercase', 'italic', 'bold', 'requirements', 'syringe', 
            'mg', 'pa', 'ql (60/30)', 'ql', 'st', 'tier', 'unknown', 'various',
            'none', 'not applicable', 'not specified', 'same', 'unclear',
            'tablet', 'capsule', 'injection', 'cream', 'ointment', 'solution',
            'oral', 'topical', 'intravenous', 'intramuscular', 'subcutaneous',"release",
            
            # NEW: Therapeutic categories and device types 
            'therapy for acne', 'wearable', 'injector', 'release(dr/ec)', 'release (dr/ec)',
            'release(ec/dr)', 'release (ec/dr)', 'ulcer therapy',
            'immunology', 'biotechnology', 'miniquick', 'vaccines', 'immunologicals',
            'therapy', 'device', 'wearable device', 'injector pen', 'delivery device',
            'technology', 'system', 'platform', 'biosimilar', 'generic version',
            
            # Medical specialties and categories
            'dermatology', 'cardiology', 'endocrinology', 'gastroenterology', 
            'rheumatology', 'oncology', 'neurology', 'psychiatry', 'infectious disease',
            'pulmonology', 'nephrology', 'hematology', 'urology', 'ophthalmology',
            
            # Therapeutic categories
            'anti-inflammatory', 'antibiotic', 'antiviral', 'antifungal', 'antihistamine',
            'analgesic', 'anesthetic', 'sedative', 'stimulant', 'antidepressant',
            
            # Device and delivery terms
            'auto-injector', 'pen device', 'inhaler device', 'pump', 'monitor',
            'meter', 'lancet', 'strip', 'cartridge', 'refill', 'disposable'
        }
        
        drug_name_lower = drug_name.lower().strip()
        if drug_name_lower in problematic_drug_names:
            #print(f"⚠️ Filtered out problematic drug name: '{drug_name}'")
            return False
        
        # Check for restriction codes and combinations
        restriction_patterns = [
            r'^(pa|st|ql)(\s*,\s*(pa|st|ql))*$',  # Pure restriction codes
            r'^ql\s*\([^)]+\)$',  # Quantity limit patterns
            r'^(pa,?\s*ql|st,?\s*ql|pa,?\s*st)$',  # Common combinations
        ]
        
        for pattern in restriction_patterns:
            if re.match(pattern, drug_name_lower):
                print(f"⚠️ Filtered out restriction code as drug name: '{drug_name}'")
                return False
        
        # Check for obvious non-medicine patterns
        invalid_patterns = [
            r'^(page|section|chapter|tier|formulary|coverage|restriction|note|example|title|header)(\s|\d|$)',
            r'^(see|refer|contact|call|visit|www\.|http)',
            r'^\d+\s*(mg|mcg|ml|%|g)(\s|$)',  # Pure dosage without drug name
            r'^(generic|brand|prior|auth|step|therapy|quantity|limit)(\s|$)',
            r'^(pa|st|ql|dl|mme)(\s|$)',  # Pure restriction codes
            r'^(tier\s*[1-5]|level\s*[1-5])(\s|$)',
            r'^(capitalized|lowercase|italic|bold|requirements)$',  # Formatting artifacts
            r'^release\s*\([^)]*dr[^)]*ec[^)]*\)$',  # Release (Dr/Ec) pattern
            r'^release\s*\([^)]*ec[^)]*dr[^)]*\)$',  # Release (Ec/Dr) pattern
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, drug_name_lower):
                #print(f"⚠️ Filtered out invalid pattern: '{drug_name}'")
                return False
        
        # Check if it looks like a valid drug name (contains letters)
        if not re.search(r'[a-zA-Z]{2,}', drug_name):
            return False
        
        # Additional check: if generic name equals drug name but is also in our problematic list
        generic_name = medicine.get('generic_name', '').strip().lower()
        if generic_name and generic_name in problematic_drug_names:
            # print(f"⚠️ Filtered out entry with problematic generic name: '{drug_name}' (generic: '{generic_name}')")
            return False
        
        # Use existing drug name validation (enhanced version)
        if not self._is_valid_drug_name(drug_name):
            print(f"⚠️ Drug name validation failed: '{drug_name}'")
            return False
        
        return True

    def debug_vector_content(self, search_term: str = None) -> Dict[str, Any]:
        """Debug method to inspect what's actually stored in the vector database."""
        if not self.vectorstore:
            return {"error": "No vectorstore available"}
        
        try:
            # Get all documents from vectorstore
            all_docs = self.vectorstore.get()
            
            debug_info = {
                "total_documents": len(all_docs.get('documents', [])),
                "sample_documents": [],
                "alternative_names_examples": [],
                "search_results": []
            }
            
            # Show sample documents
            documents = all_docs.get('documents', [])
            metadatas = all_docs.get('metadatas', [])
            
            for i, (doc, meta) in enumerate(zip(documents[:5], metadatas[:5])):
                debug_info["sample_documents"].append({
                    "index": i,
                    "content_preview": doc[:200] + "..." if len(doc) > 200 else doc,
                    "metadata": meta
                })
            
            # Look specifically for alternative names sections
            for i, doc in enumerate(documents):
                if "alternative names:" in doc.lower():
                    start = doc.lower().find("alternative names:")
                    end = min(start + 100, len(doc))
                    alt_section = doc[start:end]
                    
                    debug_info["alternative_names_examples"].append({
                        "document_index": i,
                        "alternative_names_section": alt_section,
                        "drug_name": metadatas[i].get('drug_name', 'N/A') if i < len(metadatas) else 'N/A'
                    })
            
            # If search term provided, test actual search
            if search_term and self.retriever:
                test_queries = [
                    f"Alternative names: {search_term}",
                    f"{search_term}",
                    f"Alternative names containing {search_term}"
                ]
                
                for query in test_queries:
                    try:
                        results = self.retriever.invoke(query)
                        debug_info["search_results"].append({
                            "query": query,
                            "num_results": len(results),
                            "results": [
                                {
                                    "content_preview": r.page_content[:150] + "...",
                                    "metadata": r.metadata
                                } for r in results[:3]
                            ]
                        })
                    except Exception as e:
                        debug_info["search_results"].append({
                            "query": query,
                            "error": str(e)
                        })
            
            return debug_info
            
        except Exception as e:
            return {"error": f"Debug failed: {str(e)}"}

    def _fuzzy_match(self, term1: str, term2: str, threshold: float = 0.8) -> bool:
        """Check if two terms are similar enough to be considered a match."""
        # Simple character-based similarity check
        if not term1 or not term2:
            return False
        
        # If one is significantly shorter, check if it's contained in the other
        if len(term1) < len(term2) * 0.6 or len(term2) < len(term1) * 0.6:
            shorter, longer = (term1, term2) if len(term1) < len(term2) else (term2, term1)
            return shorter in longer
        
        # Calculate simple character overlap
        chars1 = set(term1.lower())
        chars2 = set(term2.lower())
        intersection = len(chars1.intersection(chars2))
        union = len(chars1.union(chars2))
        
        if union == 0:
            return False
        
        similarity = intersection / union
        return similarity >= threshold

    def _search_by_alternative_names_direct(self, therapeutic_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Direct search through all stored documents for alternative names matches.
        This is a fallback method that doesn't rely on vector similarity.
        """
        if not self.vectorstore:
            #print(f"⚠️ DEBUG: No vectorstore available for direct alternative names search")
            return []
        
        # Extract search terms from the input drug
        search_terms = []
        drug_name = therapeutic_info.get('drug_name', '')
        generic_name = therapeutic_info.get('generic_name', '')
        active_ingredient = therapeutic_info.get('active_ingredient', '')
        
        #print(f"🔍 DEBUG: Direct alternative names search input:")
        #print(f"   - Original drug name: '{drug_name}'")
        #print(f"   - Generic name: '{generic_name}'")
        #print(f"   - Active ingredient: '{active_ingredient}'")
        
        # Collect all possible search terms
        if drug_name:
            search_terms.append(drug_name.strip())
        if generic_name:
            search_terms.append(generic_name.strip())
            # Handle multi-component generics (like "sofosbuvir/velpatasvir/voxilaprevir")
            if "/" in generic_name:
                for component in generic_name.split("/"):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
            if "," in generic_name:
                for component in generic_name.split(","):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
        if active_ingredient:
            search_terms.append(active_ingredient.strip())
            # Handle multi-component active ingredients
            if "/" in active_ingredient:
                for component in active_ingredient.split("/"):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
            if "," in active_ingredient:
                for component in active_ingredient.split(","):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
        
        # Remove empty terms, convert to lowercase, and remove duplicates
        # Also validate that each term is a proper drug name
        search_terms = list(set([term.lower().strip() for term in search_terms 
                                if term and len(term.strip()) > 2 and self._is_valid_drug_name(term)]))
        
        if not search_terms:
            #print(f"❌ DEBUG: No valid search terms found for direct alternative names search")
            return []
        
        #print(f"🎯 DEBUG: Direct search for terms: {search_terms}")
        
        try:
            # Get all documents from vectorstore
            all_docs = self.vectorstore.get()
            documents = all_docs.get('documents', [])
            metadatas = all_docs.get('metadatas', [])
            
            #print(f"📊 DEBUG: Examining {len(documents)} total documents for alternative names")
            
            alternative_matches = []
            seen_drugs = set()
            
            for doc_idx, (doc_content, metadata) in enumerate(zip(documents, metadatas)):
                if not metadata or 'drug_name' not in metadata:
                    continue
                
                found_drug_name = metadata.get('drug_name', '')
                if not found_drug_name or not self._is_valid_drug_name(found_drug_name):
                    continue
                
                # Skip if we've already found this drug (using normalized name for salt form comparison)
                normalized_drug_key = self._normalize_drug_name_for_comparison(found_drug_name)
                if normalized_drug_key in seen_drugs:
                    continue
                
                # Look for alternative names in this document
                doc_content_lower = doc_content.lower()
                
                # Find alternative names section
                alt_names_found = False
                patterns_to_search = [
                    "alternative names:",
                    "alternative names :",
                    "alternatives:",
                    "also known as:",
                    "brand names:"
                ]
                
                for pattern in patterns_to_search:
                    if pattern in doc_content_lower:
                        start_idx = doc_content_lower.find(pattern)
                        # Get the alternative names section
                        end_markers = ["|", "\n", "tier:", "restrictions:", "dosage form:"]
                        end_idx = start_idx + 300
                        
                        for marker in end_markers:
                            marker_pos = doc_content_lower.find(marker, start_idx + len(pattern))
                            if marker_pos != -1 and marker_pos < end_idx:
                                end_idx = marker_pos
                        
                        alt_names_section = doc_content_lower[start_idx:end_idx]
                        
                        # Extract the part after the colon
                        colon_idx = alt_names_section.find(":")
                        if colon_idx != -1:
                            names_part = alt_names_section[colon_idx + 1:].strip()
                            
                            # Enhanced parsing: handle both commas AND slashes as separators
                            # First split by commas, then by slashes
                            alternative_name_list = []
                            comma_split = [name.strip() for name in names_part.split(",") if name.strip()]
                            
                            for item in comma_split:
                                # Clean the item to remove dosage form parentheses first
                                cleaned_item = self._clean_drug_name_parentheses(item)
                                
                                # Check if item contains slashes (like "sofosbuvir/velpatasvir/voxilaprevir")
                                if "/" in cleaned_item:
                                    # Split by slash and add each component
                                    slash_split = [self._clean_drug_name_parentheses(sub.strip()) for sub in cleaned_item.split("/") if sub.strip()]
                                    # Only add valid drug names
                                    for sub in slash_split:
                                        if self._is_valid_drug_name(sub):
                                            alternative_name_list.append(sub)
                                    # Also keep the original combined form if it's valid
                                    if self._is_valid_drug_name(cleaned_item):
                                        alternative_name_list.append(cleaned_item)
                                else:
                                    # Only add if it's a valid drug name
                                    if self._is_valid_drug_name(cleaned_item):
                                        alternative_name_list.append(cleaned_item)
                            
                            # Remove duplicates and empty entries
                            alternative_name_list = list(set([name for name in alternative_name_list if name and len(name) > 1]))
                            
                            #print(f"      📋 DEBUG: Parsed alternative names: {alternative_name_list}")
                            
                            # Check if any of our search terms match any alternative names
                            for search_term in search_terms:
                                for alt_name in alternative_name_list:
                                    alt_name_clean = alt_name.lower().strip().replace("|", "").replace(".", "").strip()
                                    
                                    if not alt_name_clean or len(alt_name_clean) < 2:
                                        continue
                                    
                                    # Enhanced matching: exact match, partial match, or compound match
                                    search_term_lower = search_term.lower()
                                    match_found = False
                                    
                                    # Check various matching strategies
                                    if (search_term_lower == alt_name_clean or           # Exact match
                                        search_term_lower in alt_name_clean or         # Search term in alternative
                                        alt_name_clean in search_term_lower or         # Alternative in search term
                                        self._fuzzy_match(search_term_lower, alt_name_clean)):  # Fuzzy match
                                        match_found = True
                                        
                                    if match_found:
                                        # Validate the found drug name before creating entry
                                        if not self._is_valid_drug_name(found_drug_name):
                                            #print(f"      ⚠️ DEBUG: Filtered out invalid drug name from direct search result: '{found_drug_name}'")
                                            continue
                                        
                                        # Removed: medicine form "none" check - let LLM classification handle it instead
                                        
                                        seen_drugs.add(normalized_drug_key)
                                        alt_names_found = True
                                        
                                        # Create drug entry
                                        drug_entry = {
                                            'drug_name': found_drug_name,
                                            'generic_name': metadata.get('generic_name', ''),
                                            'active_ingredient': metadata.get('active_ingredient', ''),
                                            'therapeutic_class': metadata.get('therapeutic_class', ''),
                                            'tier': metadata.get('tier', ''),
                                            'restrictions': metadata.get('restrictions', ''),
                                            'dosage_form': metadata.get('dosage_form', ''),
                                            'strength': metadata.get('strength', ''),
                                            'source_document': metadata.get('source_document', ''),
                                            'match_type': 'direct_alternative_names_match',
                                            'similarity_score': 0.75,
                                            'matched_term': search_term,
                                            'matched_alternative': alt_name_clean
                                        }
                                        
                                        alternative_matches.append(drug_entry)
                                        #print(f"✅ DEBUG: DIRECT MATCH - '{found_drug_name}' via alternative name '{alt_name_clean}' for search term '{search_term}'")
                                        break
                                
                                if alt_names_found:
                                    break
                        break
            
            #print(f"🎯 DEBUG: Direct alternative names search found {len(alternative_matches)} matches")
            return alternative_matches
            
        except Exception as e:
            #print(f"❌ DEBUG: Error in direct alternative names search: {str(e)}")
            return []

    def _search_by_alternative_names_comparison(self, therapeutic_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compare drug name, generic name, and active ingredient of searched drug 
        with alternative names stored in embeddings for other medicines.
        """
        if not self.retriever:
            return []
        
        # Check cache first for this search
        search_cache_key = self._get_cache_key('vector_search', str(therapeutic_info))
        cached_result = self._get_from_cache(self.search_cache, search_cache_key)
        if cached_result is not None:
            return cached_result
        
        # Extract search terms from the input drug
        search_terms = []
        drug_name = therapeutic_info.get('drug_name', '')
        generic_name = therapeutic_info.get('generic_name', '')
        active_ingredient = therapeutic_info.get('active_ingredient', '')
        
        #print(f"🔍 DEBUG: Alternative names search input:")
        #print(f"   - Original drug name: '{drug_name}'")
        #print(f"   - Generic name: '{generic_name}'")
        #print(f"   - Active ingredient: '{active_ingredient}'")
        
        # Collect all possible search terms
        if drug_name:
            search_terms.append(drug_name.strip())
        if generic_name:
            search_terms.append(generic_name.strip())
            # Handle multi-component generics (like "sofosbuvir/velpatasvir/voxilaprevir")  
            if "/" in generic_name:
                for component in generic_name.split("/"):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
            if "," in generic_name:
                for component in generic_name.split(","):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
        if active_ingredient:
            search_terms.append(active_ingredient.strip())
            # Handle multi-component active ingredients
            if "/" in active_ingredient:
                for component in active_ingredient.split("/"):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
            if "," in active_ingredient:
                for component in active_ingredient.split(","):
                    if component.strip() and self._is_valid_drug_name(component.strip()):
                        search_terms.append(component.strip())
        
        # Remove empty terms, convert to lowercase, and remove duplicates
        # Also validate that each term is a proper drug name
        search_terms = list(set([term.lower().strip() for term in search_terms 
                                if term and len(term.strip()) > 2 and self._is_valid_drug_name(term)]))
        
        if not search_terms:
            #print(f"❌ DEBUG: No valid search terms found for alternative names search")
            return []
        
        #print(f"🎯 DEBUG: Searching alternative names for terms: {search_terms}")
        
        alternative_matches = []
        
        try:
            # Prepare all query combinations for parallel execution
            all_query_combinations = []
            for search_term in search_terms:
                queries = [
                    f"Alternative names: {search_term}",
                    f"Alternative names containing {search_term}",
                    f"{search_term} brand name generic equivalent alternative"
                ]
                for query in queries:
                    all_query_combinations.append((search_term, query))
            
            # Execute all queries in parallel
            def execute_search_query(search_term_query_tuple):
                """Execute a single search query and return processed results."""
                search_term, query = search_term_query_tuple
                try:
                    #print(f"   🔍 DEBUG: Executing query: '{query}' for term '{search_term}'")
                    docs = self.retriever.invoke(query)
                    return search_term, query, docs
                except Exception as e:
                    #print(f"      ⚠️ DEBUG: Query failed for '{query}': {str(e)}")
                    return search_term, query, []
            
            with ThreadPoolExecutor(max_workers=6) as executor:
                # Submit all query combinations for parallel execution
                query_futures = [executor.submit(execute_search_query, combo) for combo in all_query_combinations]
                
                # Process results as they complete
                for future in as_completed(query_futures):
                    try:
                        search_term, query, docs = future.result()
                        #print(f"   � DEBUG: Query returned {len(docs)} documents for term '{search_term}'")
                        
                        for i, doc in enumerate(docs):
                            metadata = doc.metadata
                            if not metadata or 'drug_name' not in metadata:
                                #print(f"      ⚠️ DEBUG: Document {i+1} has no valid metadata")
                                continue
                            
                            # Extract drug information from metadata
                            found_drug_name = metadata.get('drug_name', '')
                            found_generic = metadata.get('generic_name', '')
                            found_ingredient = metadata.get('active_ingredient', '')
                            
                            #print(f"      📋 DEBUG: Document {i+1} - Drug: '{found_drug_name}', Generic: '{found_generic}', Ingredient: '{found_ingredient}'")
                            
                            # Skip if invalid drug name
                            if not found_drug_name or not self._is_valid_drug_name(found_drug_name):
                                #print(f"      ❌ DEBUG: Invalid drug name: '{found_drug_name}'")
                                continue
                            
                            # Check if this drug actually contains our search term in its alternative names
                            # by looking at the document content for "Alternative names:" section
                            doc_content = doc.page_content.lower()
                            alt_names_section = ""
                            
                            # Look for alternative names section with different possible formats
                            patterns_to_search = [
                                "alternative names:",
                                "alternative names :",
                                "alternatives:",
                                "also known as:",
                                "brand names:"
                            ]
                            
                            for pattern in patterns_to_search:
                                if pattern in doc_content:
                                    start_idx = doc_content.find(pattern)
                                    # Get the alternative names section (look for next section separator or newline)
                                    end_markers = ["|", "\n", "tier:", "restrictions:", "dosage form:"]
                                    end_idx = start_idx + 300  # Default fallback
                                    
                                    for marker in end_markers:
                                        marker_pos = doc_content.find(marker, start_idx + len(pattern))
                                        if marker_pos != -1 and marker_pos < end_idx:
                                            end_idx = marker_pos
                                    
                                    alt_names_section = doc_content[start_idx:end_idx]
                                    #print(f"      🎯 DEBUG: Alternative names section found with pattern '{pattern}': '{alt_names_section[:100]}...'")
                                    break
                            
                            # Extract just the alternative names list (after the colon)
                            term_found_in_alt_names = False
                            if alt_names_section:
                                # Extract the part after the colon
                                colon_idx = alt_names_section.find(":")
                                if colon_idx != -1:
                                    names_part = alt_names_section[colon_idx + 1:].strip()
                                    # Split by commas and clean each name, then check each alternative name
                                    raw_alternative_names = [name.strip() for name in names_part.split(",") if name.strip()]
                                    alternative_name_list = []
                                    
                                    # Clean each name and validate before adding
                                    for raw_name in raw_alternative_names:
                                        cleaned_name = self._clean_drug_name_parentheses(raw_name)
                                        if self._is_valid_drug_name(cleaned_name):
                                            alternative_name_list.append(cleaned_name)
                                    
                                    #print(f"      📋 DEBUG: Parsed alternative names: {alternative_name_list}")
                                    
                                    # Check if our search term matches any of the individual alternative names
                                    search_term_lower = search_term.lower()
                                    for alt_name in alternative_name_list:
                                        alt_name_clean = alt_name.lower().strip()
                                        # Remove any extra characters that might be present
                                        alt_name_clean = alt_name_clean.replace("|", "").replace(".", "").strip()
                                        
                                        # Skip empty names
                                        if not alt_name_clean or len(alt_name_clean) < 2:
                                            continue
                                        
                                        # Check for exact match or partial match (both ways)
                                        if (search_term_lower == alt_name_clean or 
                                            search_term_lower in alt_name_clean or 
                                            alt_name_clean in search_term_lower):
                                            term_found_in_alt_names = True
                                            #print(f"      ✅ DEBUG: MATCH - '{search_term}' matches alternative name '{alt_name_clean}'")
                                            break
                                    
                                    if not term_found_in_alt_names:
                                        #print(f"      ❌ DEBUG: No match - '{search_term}' not found in alternative names: {alternative_name_list}")
                                        pass
                            else:
                                #print(f"      ⚠️ DEBUG: No alternative names section found in document")
                                pass

                            if term_found_in_alt_names:
                                # Validate the found drug name before creating entry
                                if not self._is_valid_drug_name(found_drug_name):
                                    #print(f"      ⚠️ DEBUG: Filtered out invalid drug name from search result: '{found_drug_name}'")
                                    pass
                                    continue
                                
                                # Create drug entry with metadata - show all results including duplicates
                                drug_entry = {
                                    'drug_name': found_drug_name,
                                    'generic_name': found_generic or '',
                                    'active_ingredient': found_ingredient or '',
                                    'therapeutic_class': metadata.get('therapeutic_class', ''),
                                    'tier': metadata.get('tier', ''),
                                    'restrictions': metadata.get('restrictions', ''),
                                    'dosage_form': metadata.get('dosage_form', ''),
                                    'strength': metadata.get('strength', ''),
                                    'source_document': metadata.get('source_document', ''),
                                    'match_type': 'alternative_names_match',
                                    'similarity_score': 0.7,  # Good confidence for alternative names match
                                    'matched_term': search_term,
                                    'search_query': query
                                }
                                
                                alternative_matches.append(drug_entry)
                                #print(f"      ✅ DEBUG: MATCH FOUND - '{found_drug_name}' via alternative names for term '{search_term}'")
                            else:
                                #print(f"      ❌ DEBUG: Term '{search_term}' NOT found in alternative names section")
                                pass
                    except Exception as e:
                        #print(f"⚠️ DEBUG: Alternative search processing failed: {str(e)}")
                        pass
            
            #print(f"🎯 DEBUG: Alternative names comparison SUMMARY:")
            #print(f"   - Input terms searched: {search_terms}")
            #print(f"   - Total matches found: {len(alternative_matches)}")
            
            #if alternative_matches:
                #print(f"   - Matches details:")
                #for i, match in enumerate(alternative_matches, 1):
                    #print(f"     {i}. {match['drug_name']} (matched via '{match['matched_term']}')")

            #else:
                #print(f"   - No matches found in alternative names")
            
            return alternative_matches
            
        except Exception as e:
            #print(f"❌ DEBUG: Error in alternative names comparison: {str(e)}")
            return []

    def get_vector_similarity_scores(self, drug_name: str, alternatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimized similarity scoring with caching and parallel processing."""
        #print(f"🔍 DEBUG: Getting vector similarity scores for {len(alternatives)} alternatives")
        
        if not self.retriever:
            #print(f"⚠️ DEBUG: Vector retriever not available")
            return alternatives
        
        # Check cache for similarity scores
        sim_cache_key = self._get_cache_key('similarity', drug_name.lower(), len(alternatives))
        cached_similarity = self._get_from_cache(self.similarity_cache, sim_cache_key)
        
        if cached_similarity is not None and len(cached_similarity) == len(alternatives):
            #print(f"🎯 DEBUG: Using cached similarity scores")
            return cached_similarity
        
        try:
            # Prioritize most effective queries based on drug complexity
            base_queries = [
                f"Alternative names: {drug_name}",
                f"{drug_name} generic name equivalent substitute"
            ]
            
            # Add complex queries only for non-exact matches or complex drug names
            if len(alternatives) > 1 or len(drug_name.split()) > 1:
                base_queries.extend([
                    f"Find alternatives and similar drugs to {drug_name}",
                    f"Therapeutic equivalent of {drug_name}"
                ])
            
            # Get relevant documents from vector store using parallel queries with caching
            all_retrieved_docs = []
            
            def execute_vector_query_cached(query):
                """Execute a cached vector query."""
                query_cache_key = self._get_cache_key('vec_query', query)
                cached_docs = self._get_from_cache(self.embedding_cache, query_cache_key)
                
                if cached_docs is not None:
                    return cached_docs
                
                try:
                    docs = self.retriever.invoke(query)
                    self._set_cache(self.embedding_cache, query_cache_key, docs)
                    return docs
                except Exception as e:
                    #print(f"⚠️ DEBUG: Query '{query}' failed: {str(e)}")
                    return []
            
            # Use dynamic thread count based on query complexity
            thread_count = min(len(base_queries), self.max_workers // 2)
            
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                # Submit all queries for parallel execution
                query_futures = [executor.submit(execute_vector_query_cached, query) for query in base_queries]
                
                # Collect results as they complete with timeout
                try:
                    for future in as_completed(query_futures, timeout=15):
                        try:
                            docs = future.result()
                            all_retrieved_docs.extend(docs)
                        except Exception as e:
                            #print(f"⚠️ DEBUG: Vector query processing failed: {str(e)}")
                            pass
                except Exception as timeout_e:
                    #print(f"⚠️ DEBUG: Vector query timeout: {str(timeout_e)}")
                    pass
            
            # Remove duplicates based on content
            seen_content = set()
            retrieved_docs = []
            for doc in all_retrieved_docs:
                content_hash = hash(doc.page_content)
                if content_hash not in seen_content:
                    retrieved_docs.append(doc)
                    seen_content.add(content_hash)
            #print(f"📊 DEBUG: Retrieved {len(retrieved_docs)} documents from vector store")
            
            # Calculate similarity scores for each alternative
            for alt in alternatives:
                alt_name = alt.get('drug_name', '').lower()
                alt_generic = alt.get('generic_name', '').lower()
                alt_ingredient = alt.get('active_ingredient', '').lower()
                
                # Check if alternative appears in retrieved documents
                vector_score = 0.0
                doc_matches = 0
                
                for doc in retrieved_docs:
                    content = doc.page_content.lower()
                    if (alt_name in content or alt_generic in content or alt_ingredient in content):
                        doc_matches += 1
                        # Higher score for more document matches
                        vector_score = min(1.0, doc_matches * 0.2)
                
                # Combine with existing similarity score
                existing_score = alt.get('similarity_score', 0.5)
                combined_score = (existing_score + vector_score) / 2
                alt['vector_similarity'] = vector_score
                alt['combined_similarity'] = combined_score
                alt['document_matches'] = doc_matches
                
                #print(f"📊 DEBUG: {alt_name} - Vector: {vector_score:.2f}, Combined: {combined_score:.2f}")
            
            # Cache the results for future use
            self._set_cache(self.similarity_cache, sim_cache_key, alternatives)
            return alternatives
            
        except Exception as e:
            #print(f"❌ DEBUG: Error calculating vector similarities: {str(e)}")
            return alternatives

    def find_drug_alternatives(self, drug_name: str) -> Dict[str, Any]:
        """Enhanced drug alternative finding with caching and AI-driven therapeutic equivalents."""
        # NEW: Handle complex queries with patient context
        full_query = drug_name
        clean_drug_name = drug_name
        if " for a patient with " in drug_name:
            context_part = drug_name.split(" for a patient with ")[1]
            clean_drug_name = drug_name.split(" for a patient with ")[0].strip()
            print(f"BRAIN DEBUG: Patient context detected: {context_part}")
            print(f"BRAIN DEBUG: The AI Search Engine will prioritize finding alternatives that are SAFE for this patient context.")
        
        # Use clean_drug_name for exact checks, but keep full_query for LLM
        drug_name = clean_drug_name 

        #print(f"\n🚀 DEBUG: Starting enhanced drug alternative search for '{drug_name}' (Full: '{full_query}')")
        start_time = datetime.now()
        
        # Step -1: Check full result cache first - Use full_query to ensure context-aware caching
        full_cache_key = self._get_cache_key('full_search', full_query.lower())
        cached_full_result = self._get_from_cache(self.search_cache, full_cache_key)
        if cached_full_result is not None:
            #print(f"🎯 DEBUG: Using cached full search result for '{drug_name}'")
            # Update timestamps in cached result
            cached_full_result['search_timestamp'] = datetime.now().isoformat()
            return cached_full_result
        
        # Step 0: Basic input validation - MADE VERY PERMISSIVE FOR 100% ACCURACY
        # Only reject completely empty inputs or single characters
        if not drug_name or len(drug_name.strip()) < 2:
            #print(f"❌ DEBUG: Invalid drug name entered: '{drug_name}'")
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Provide helpful suggestions based on what was entered
            suggestions = self._get_input_suggestions(drug_name)
            
            error_result = {
                "error": "Invalid drug name",
                "message": f"'{drug_name}' is not a valid medication name. Please enter a proper drug name (e.g., Ozempic, Lisinopril, Metformin).",
                "suggestions": suggestions,
                "therapeutic_info": {
                    "generic_name": "N/A",
                    "active_ingredient": "N/A",
                    "therapeutic_class": "N/A",
                    "therapeutic_equivalents": [],
                    "indication": "N/A",
                    "mechanism": "N/A"
                },
                "formulary_alternatives": [],
                "rag_analysis": {
                    "answer": "The entered text does not appear to be a valid medication name.",
                    "source_documents": [],
                    "num_sources": 0
                },
                "total_alternatives": 0,
                "processing_time": processing_time,
                "search_timestamp": datetime.now().isoformat(),
                "status": "not_found"
            }
            
            # Don't cache error results
            return error_result
        
        # Step 0.5: Check for EXACT match first
        # If found, return immediately ONLY if no patient context is provided.
        # If patient context exists, we MUST search for alternatives because the exact match might be unsafe.
        print(f"INFO DEBUG: Step 0.5 - Checking for exact match in formulary")
        exact_matches = []
        found_exact_in_formulary = False
        
        # Detect if we have patient context in the query
        has_patient_context = " for a patient with " in full_query
        
        # Use ONLY the original drug name for exact matching to prevent false positives
        original_drug_name_lower = drug_name.lower().strip()
        original_normalized_name = self._normalize_drug_name_for_comparison(drug_name)
        
        print(f"SEARCH DEBUG: Searching for exact match: '{drug_name}'")
        
        # Search through all drugs in the database for exact name match
        for ingredient, drugs in self.drug_database.items():
            for drug in drugs:
                drug_name_match = drug.get('drug_name', '').lower().strip()
                generic_name_match = drug.get('generic_name', '').lower().strip()
                
                normalized_drug_name = self._normalize_drug_name_for_comparison(drug.get('drug_name', ''))
                normalized_generic_name = self._normalize_drug_name_for_comparison(drug.get('generic_name', ''))
                
                if (original_drug_name_lower == drug_name_match or 
                    original_drug_name_lower == generic_name_match or
                    original_normalized_name == normalized_drug_name or
                    original_normalized_name == normalized_generic_name):
                    
                    # Data quality validation
                    is_drug_name_match = (original_drug_name_lower == drug_name_match or 
                                        original_normalized_name == normalized_drug_name)
                    is_generic_name_match = (original_drug_name_lower == generic_name_match or 
                                           original_normalized_name == normalized_generic_name)
                    
                    if is_generic_name_match and not is_drug_name_match:
                        actual_drug_name = drug.get('drug_name', '').lower().strip()
                        search_name_normalized = self._normalize_drug_name_for_comparison(original_drug_name_lower)
                        drug_name_normalized = self._normalize_drug_name_for_comparison(actual_drug_name)
                        
                        search_words = set(search_name_normalized.split())
                        drug_words = set(drug_name_normalized.split())
                        common_words = search_words.intersection(drug_words)
                        
                        if len(common_words) == 0 and len(search_words) > 0 and len(drug_words) > 0:
                            continue  # Skip likely bad data match
                    
                    exact_matches.append(drug)
                    found_exact_in_formulary = True
        
        # Return immediately if exact matches found AND NO patient context
        if exact_matches and not has_patient_context:
            print(f"SUCCESS DEBUG: Exact match found and no patient context - returning instantly")
            return self._create_exact_match_response(drug_name, exact_matches, start_time)
        elif exact_matches and has_patient_context:
            print(f"BRAIN DEBUG: Exact match found but patient context present - searching for alternatives to ensure safety")
        
        # Step 0.7: Fuzzy Match Optimization - If not exact, check for near matches
        # This speeds up searches for "Aspirin" when we only have "Aspirin 81mg"
        print(f"INFO DEBUG: Step 0.7 - Checking for fuzzy matches in local database")
        fuzzy_matches = []
        if not exact_matches:
            from difflib import SequenceMatcher
            
            search_name = original_normalized_name
            # Search all drugs for close name matches
            for ingredient, drugs in self.drug_database.items():
                for drug in drugs:
                    target_name = self._normalize_drug_name_for_comparison(drug.get('drug_name', ''))
                    # Simple check: is one a subset of the other or very similar?
                    if search_name in target_name or target_name in search_name:
                        ratio = SequenceMatcher(None, search_name, target_name).ratio()
                        if ratio > 0.8:
                            drug_copy = drug.copy()
                            drug_copy['similarity_score'] = ratio
                            fuzzy_matches.append(drug_copy)
            
            if fuzzy_matches:
                fuzzy_matches.sort(key=lambda x: x['similarity_score'], reverse=True)
                # If we found a very strong fuzzy match (>95%), treat it as an exact match to skip AI
                if fuzzy_matches[0]['similarity_score'] > 0.95:
                    print(f"TARGET DEBUG: High-confidence fuzzy match found ({fuzzy_matches[0]['similarity_score']:.2f}) - treating as covered.")
                    exact_matches = [fuzzy_matches[0]]
                    # Return immediately for high-confidence fuzzy match
                    print(f"SUCCESS DEBUG: Returning early for high-confidence fuzzy match.")
                    return self._create_exact_match_response(drug_name, exact_matches, start_time)
        
        # No exact match found - proceed to search for alternatives
        # NOW we can use base drug name for alternative searching (strip numbers)
        base_drug_name = re.split(r'\s*\d', drug_name)[0].strip() if drug_name else drug_name
        print(f"INFO DEBUG: No exact match found for '{drug_name}' - proceeding with alternative search")
        print(f"INFO DEBUG: Using base name '{base_drug_name}' for alternative searching")
        
        # Step 1: Get therapeutic information using AI (enhanced with alternative names search)
        #print(f"📋 DEBUG: Step 1 - Getting therapeutic information")
        
        # First try to find the drug directly to ensure it exists
        direct_matches = self.simple_search_drug(base_drug_name)
        if not direct_matches:
            # Try alternative names search if direct match fails
            #print(f"📋 DEBUG: Step 1b - Searching via alternative names in embeddings")
            direct_matches = self.search_by_alternative_names(base_drug_name)
        
        if direct_matches:
            # Use the found drug's information to enhance therapeutic info
            found_drug = direct_matches[0]
            #print(f"✅ DEBUG: Found drug in formulary: {found_drug.get('drug_name', 'N/A')}")
        
        therapeutic_info = self.get_generic_and_therapeutic_equivalents(base_drug_name, full_query=full_query)
        
        # Add the original drug name to therapeutic info for alternative names comparison
        therapeutic_info['drug_name'] = base_drug_name
        therapeutic_info['original_search_term'] = drug_name  # Keep original for display
        
        # Step 2: Check alternatives in formulary database  
        #print(f"📋 DEBUG: Step 2 - Checking alternatives in formulary")
        formulary_alternatives = self.check_alternatives_in_formulary(therapeutic_info)
        
        # Step 3: Get vector similarity scores
        #print(f"📋 DEBUG: Step 3 - Getting vector similarity scores")
        scored_alternatives = self.get_vector_similarity_scores(base_drug_name, formulary_alternatives)
        
        # Step 4: Sort by combined similarity score
        #print(f"📋 DEBUG: Step 4 - Sorting by combined similarity score")
        scored_alternatives.sort(key=lambda x: x.get('combined_similarity', 0), reverse=True)
        
        # Step 4.5: Add suitable tags to alternatives
        #print(f"📋 DEBUG: Step 4.5 - Adding suitable tags to alternatives")
        for alternative in scored_alternatives:
            alternative['tags'] = self._generate_suitable_tags(alternative, therapeutic_info)
        
        # ===== STEP 5 DISABLED: RAG analysis for additional context =====
        # NOTE: To re-enable, uncomment the lines below and update the return statement
        # Step 5: Get RAG analysis for additional context
        # #print(f"📋 DEBUG: Step 5 - Getting RAG analysis")
        # query = f"What is the active ingredient in {base_drug_name} and what alternatives are available in the formulary?"
        # rag_result = self.query(query)
        rag_result = {"answer": "RAG analysis disabled", "source_documents": [], "num_sources": 0}
        #print(f"📋 DEBUG: Step 5 - RAG analysis Disabled")
        # ===== END STEP 5 DISABLED =====
        
        # Step 6: Validate alternatives with Doctor's AI Assistant
        #print(f"📋 DEBUG: Step 6 - Validating alternatives with Doctor's AI Assistant")
        #print(f"🚀 DEBUG: Sending {len(scored_alternatives)} alternatives to AI for validation:")
        for i, alt in enumerate(scored_alternatives, 1):
            match_type = alt.get('match_type', 'unknown')
            similarity = alt.get('combined_similarity', 0)
            #print(f"   {i}. {alt.get('drug_name', 'N/A')} (type: {match_type}, similarity: {similarity:.3f})")
        
        # OPTIMIZATION: Skip AI validation to reduce completion API latency 
        # This removes the expensive gpt-4o-mini calls that add reasoning/recommendation descriptions
        validated_alternatives = scored_alternatives[:10]  # Take top 10, no AI filtering needed
        
        # Step 7: Final LLM validation to filter out non-medicines
        #print(f"📋 DEBUG: Step 7 - Final LLM validation to filter out non-medicines")
        # final_medicine_alternatives = self._filter_non_medicines_with_llm(validated_alternatives)
        final_medicine_alternatives = [
            alt for alt in validated_alternatives
            if self._is_valid_drug_name(alt.get('drug_name', '')) 
            and self._is_valid_medicine_entry(alt)
        ]
        # Step 8: Group drugs with same name but different forms and create consolidated entries
        #print(f"📋 DEBUG: Step 8 - Grouping drugs with same name but different forms")
        grouped_alternatives = self._group_medicines_by_base_name(final_medicine_alternatives)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        #print(f"✅ DEBUG: Completed alternative search in {processing_time:.2f} seconds")
        #print(f"📊 DEBUG: Found {len(grouped_alternatives)} grouped alternatives (from {len(final_medicine_alternatives)} individual forms, filtered from {len(scored_alternatives)} candidates)")
        
        final_result = {
            "therapeutic_info": therapeutic_info,
            "formulary_alternatives": grouped_alternatives,
            "rag_analysis": rag_result,
            "total_alternatives": len(grouped_alternatives),
            "original_candidates": len(scored_alternatives),
            "processing_time": processing_time,
            "search_timestamp": end_time.isoformat(),
            "is_exact_match": found_exact_in_formulary
        }
        
        # Cache the final result for future identical searches
        self._set_cache(self.search_cache, full_cache_key, final_result)
        return final_result

    def _create_exact_match_response(self, drug_name: str, exact_matches: List[Dict[str, Any]], start_time: datetime) -> Dict[str, Any]:
        """Helper to create a standardized exact match response."""
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"TARGET DEBUG: Exact/High-confidence match found for '{drug_name}'")
        
        enhanced_exact_matches = []
        for exact_drug in exact_matches:
            enhanced_drug = exact_drug.copy()
            enhanced_drug['similarity_score'] = enhanced_drug.get('similarity_score', 1.00)
            enhanced_drug['combined_similarity'] = enhanced_drug.get('combined_similarity', 1.00)
            enhanced_drug['validation_score'] = 100
            enhanced_drug['validation_confidence'] = 1.00
            enhanced_drug['validation_status'] = 'EXACT_MATCH'
            enhanced_drug['match_type'] = 'exact_drug_name'
            enhanced_drug['ai_reasoning'] = f"Match found: '{drug_name}' exists in the formulary."
            enhanced_exact_matches.append(enhanced_drug)
        
        exact_drug = enhanced_exact_matches[0]
        therapeutic_info = {
            "drug_name": drug_name,
            "generic_name": exact_drug.get('generic_name', drug_name),
            "active_ingredient": exact_drug.get('active_ingredient', drug_name.lower()),
            "therapeutic_class": exact_drug.get('therapeutic_class', 'Unknown'),
            "therapeutic_equivalents": [],
            "indication": "Original medicine found in formulary",
            "mechanism": exact_drug.get('therapeutic_class', 'Unknown')
        }
        
        return {
            "message": f"✅ Great news! '{drug_name}' is covered in your formulary.",
            "therapeutic_info": therapeutic_info,
            "formulary_alternatives": self._group_medicines_by_base_name(enhanced_exact_matches),
            "rag_analysis": {
                "answer": f"The requested medication '{drug_name}' is available in the formulary.",
                "source_documents": [],
                "num_sources": 0
            },
            "total_alternatives": len(exact_matches),
            "processing_time": processing_time,
            "search_timestamp": end_time.isoformat(),
            "status": "exact_match_found",
            "is_exact_match": True
        }

    def get_database_summary(self) -> Dict[str, Any]:
        """Get summary of loaded formulary data."""
        total_drugs = sum(len(drugs) for drugs in self.drug_database.values())
        unique_ingredients = len(self.drug_database.keys())

        tier_counts = {}
        for drugs in self.drug_database.values():
            for drug in drugs:
                tier = drug.get('tier', 'Unknown')
                tier_counts[tier] = tier_counts.get(tier, 0) + 1

        return {
            "total_drugs": total_drugs,
            "unique_active_ingredients": unique_ingredients,
            "tier_distribution": tier_counts,
            "documents_processed": list(set(drug.get('source_document', '')
                                          for drugs in self.drug_database.values()
                                          for drug in drugs))
        }

    def extract_unique_medicine_entries_from_vectorstore(self) -> list[Dict[str, Any]]:
        """
        Extract unique medicine entries from ChromaDB metadata directly.
        Returns a flat list of drugs with normalized fields.
        """
        if not self.vectorstore:
            return []

        try:
            results = self.vectorstore.get(include=['metadatas'])
            metadatas = results.get('metadatas', []) or []
            unique_entries = {}

            for meta in metadatas:
                drug_name = str(meta.get('drug_name', '') or '').strip()
                if not drug_name:
                    continue

                generic_name = str(meta.get('generic_name', '') or '').strip()
                medicine_form = str(meta.get('medicine_form', '') or '').strip() or 'Tablet'
                key = (drug_name.lower(), generic_name.lower(), medicine_form.lower())

                if key in unique_entries:
                    continue

                unique_entries[key] = {
                    'drug_name': drug_name,
                    'generic_name': generic_name,
                    'therapeutic_class': meta.get('therapeutic_class', 'Unknown'),
                    'strength': meta.get('strength', 'N/A'),
                    'dosage_form': medicine_form,
                    'availability': 'Formulary' if meta.get('tier') else 'Non Formulary',
                    'tier': meta.get('tier', 'Unknown'),
                    'restrictions': meta.get('restrictions', 'None'),
                    # Keep aliases for frontend compatibility if needed
                    'name': drug_name,
                    'genericName': generic_name,
                    'class': meta.get('therapeutic_class', 'Unknown'),
                    'form': medicine_form
                }

            return sorted(unique_entries.values(), key=lambda x: x.get('drug_name', ''))
        except Exception:
            return []

    def debug_search(self, drug_name: str) -> Dict[str, Any]:
        """Debug function to show what's happening during search."""
        debug_info = {
            "search_term": drug_name,
            "database_stats": {
                "total_active_ingredients": len(self.drug_database),
                "total_drugs": sum(len(drugs) for drugs in self.drug_database.values())
            },
            "raw_text_length": len(self.raw_text_content),
            "search_results": []
        }

        simple_results = self.simple_search_drug(drug_name)
        debug_info["simple_search_results"] = len(simple_results)

        if simple_results:
            debug_info["search_results"] = simple_results[:3]

        debug_info["sample_drugs"] = []
        count = 0
        for ingredient, drugs in self.drug_database.items():
            if count >= 5:
                break
            for drug in drugs[:2]:
                debug_info["sample_drugs"].append({
                    "ingredient": ingredient,
                    "drug_name": drug.get('drug_name', 'N/A'),
                    "tier": drug.get('tier', 'N/A')
                })
                count += 1
                if count >= 5:
                    break
