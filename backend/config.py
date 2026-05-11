"""
Configuration file for Clinical Agent RAG system.
Defines global paths and settings.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"

DATABASE_DIR = DATA_DIR / "database" / "formulary_chroma_db"
PDF_DIR = DATA_DIR / "pdfs"
JSON_DIR = DATA_DIR / "json"

# Specific file paths
FORMULARY_PDF_PATH = PDF_DIR / "formulary1.pdf"
LEGACY_PDF_PATH = DATA_DIR / "formulary1.pdf"  # For backward compatibility

# Database configuration
CHROMA_DB_PATH = str(DATABASE_DIR)

# OpenAI configuration
OPENAI_CONFIG = {
    'MODEL_NAME': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
    'EMBEDDING_MODEL': os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large'),
    'API_KEY': os.getenv('OPENAI_API_KEY', '')
}

# PDF processing library availability
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# Enhanced PDF Processor configuration
APP_CONFIG = {
    'data_folder': str(PDF_DIR),
    'cache_folder': str(BASE_DIR / 'cache'),
    'cache_file': 'pdf_cache.json'
}

# Medical processing configuration
MEDICAL_CONFIG = {
    'min_content_length': 50,
    'min_medical_indicators': 2
}

# File paths for environment variables
ENV_PATHS = {
    'DATA_DIR': str(DATA_DIR),
    'DATABASE_DIR': str(DATABASE_DIR),
    'PDF_DIR': str(PDF_DIR),
    'JSON_DIR': str(JSON_DIR),
    'FORMULARY_DOCUMENTS': str(FORMULARY_PDF_PATH) if FORMULARY_PDF_PATH.exists() else str(LEGACY_PDF_PATH)
}

def ensure_directories():
    """Create necessary directories if they don't exist."""
    directories = [DATA_DIR, DATABASE_DIR, PDF_DIR, JSON_DIR]
    
    created_count = 0
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_count += 1
    
    if created_count > 0:
        print(f"Created {created_count} required directories")
    else:
        print("All required directories already exist")

def get_formulary_documents():
    """Get list of available formulary documents."""
    documents = []
    
    # Check for PDFs in the pdf directory
    if PDF_DIR.exists():
        pdf_files = list(PDF_DIR.glob("*.pdf"))
        documents.extend([str(pdf) for pdf in pdf_files])
    
    # Check for legacy PDF in data directory
    if LEGACY_PDF_PATH.exists() and str(LEGACY_PDF_PATH) not in documents:
        documents.append(str(LEGACY_PDF_PATH))
    
    return documents

def move_legacy_files():
    """Move legacy files to organized structure."""
    moved_files = []
    
    # Move formulary1.pdf from Data/ to Data/pdfs/
    if LEGACY_PDF_PATH.exists() and not FORMULARY_PDF_PATH.exists():
        ensure_directories()
        LEGACY_PDF_PATH.rename(FORMULARY_PDF_PATH)
        moved_files.append(f"Moved {LEGACY_PDF_PATH} -> {FORMULARY_PDF_PATH}")
    
    # Move any JSON files from root to Data/json/
    for json_file in BASE_DIR.glob("*.json"):
        target = JSON_DIR / json_file.name
        if not target.exists():
            json_file.rename(target)
            moved_files.append(f"Moved {json_file} -> {target}")
    
    return moved_files

if __name__ == "__main__":
    # Initialize directory structure when run directly
    print("Setting up Clinical Agent RAG directory structure...")
    ensure_directories()
    
    moved = move_legacy_files()
    if moved:
        print("Files moved:")
        for move in moved:
            print(f"   {move}")
    
    documents = get_formulary_documents()
    if documents:
        print("Available formulary documents:")
        for doc in documents:
            print(f"   - {doc}")
    else:
        print("No formulary documents found!")
    
    print(f"\nConfiguration paths:")
    for key, value in ENV_PATHS.items():
        print(f"   {key}: {value}")
