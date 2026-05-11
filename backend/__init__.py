"""
Backend module for Formulary Drug RAG Application
Contains all core business logic, RAG processing, and API handlers
"""

from .cache_manager import PDFCacheManager
from .config import (
    BASE_DIR, DATA_DIR, DATABASE_DIR, PDF_DIR, JSON_DIR,
    OPENAI_CONFIG, APP_CONFIG, MEDICAL_CONFIG,
    ensure_directories, get_formulary_documents, move_legacy_files
)
from .otel_config import ResilientOTelConfig, init_telemetry, get_tracer, get_meter
from .formulary_drug_rag import FormularyDrugRAG
from .rxnorm_api import RxNormAPI, TherapeuticClassFilter
from .medical_processor import MedicalTextProcessor
from .medicine_models import MedicineEntry, MedicineList, MedicineExtractionResponse
from .pdf_processor import EnhancedPDFProcessor

__all__ = [
    'PDFCacheManager',
    'BASE_DIR', 'DATA_DIR', 'DATABASE_DIR', 'PDF_DIR', 'JSON_DIR',
    'OPENAI_CONFIG', 'APP_CONFIG', 'MEDICAL_CONFIG',
    'ensure_directories', 'get_formulary_documents',
    'ResilientOTelConfig', 'init_telemetry', 'get_tracer', 'get_meter',
    'FormularyDrugRAG',
    'RxNormAPI', 'TherapeuticClassFilter',
    'MedicalTextProcessor',
    'MedicineEntry', 'MedicineList', 'MedicineExtractionResponse',
    'EnhancedPDFProcessor'
]
