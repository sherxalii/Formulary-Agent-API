"""
Medical Text Processor
Specialized processor for medical/pharmaceutical text processing and normalization
"""

import re
from typing import List, Dict
from .config import MEDICAL_CONFIG


class MedicalTextProcessor:
    """Specialized processor for medical/pharmaceutical text"""
    
    def __init__(self):
        # Comprehensive medical terminology
        self.drug_name_patterns = [
            r'\b[A-Z][a-z]+(?:-[A-Z][a-z]+)*\s*(?:\d+\.?\d*\s*(?:mg|mcg|g|ml|units?))?',  # Drug names with dosages
            r'\b(?:generic|brand):\s*([A-Za-z\-\s]+)',  # Generic/brand labels
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:tablets?|capsules?|injection)',  # Drug forms
        ]
        
        self.medical_abbreviations = {
            'mg': 'milligrams', 'mcg': 'micrograms', 'g': 'grams',
            'ml': 'milliliters', 'tab': 'tablet', 'cap': 'capsule',
            'bid': 'twice daily', 'tid': 'three times daily', 'qid': 'four times daily',
            'po': 'by mouth', 'iv': 'intravenous', 'im': 'intramuscular'
        }
        
        self.medical_indicators = [
            'mg', 'ml', 'tablet', 'capsule', 'dose', 'dosage', 'medication', 'drug',
            'prescription', 'generic', 'brand', 'formulary', 'coverage', 'tier',
            'copay', 'prior authorization', 'quantity limit', 'pharmacy', 'prescription',
            'treatment', 'therapeutic', 'clinical', 'patient'
        ]
    
    def normalize_drug_names(self, text: str) -> str:
        """Normalize drug names for consistent matching"""
        if not text:
            return ""
            
        # Convert to lowercase for processing
        normalized = text.lower()
        
        # Expand common abbreviations
        for abbr, full in self.medical_abbreviations.items():
            normalized = re.sub(rf'\b{abbr}\b', full, normalized)
        
        # Standardize dosage formats
        normalized = re.sub(r'(\d+)\s*mg\b', r'\1 milligrams', normalized)
        normalized = re.sub(r'(\d+)\s*mcg\b', r'\1 micrograms', normalized)
        
        return normalized
    
    def extract_drug_entries(self, text: str) -> List[Dict]:
        """Extract structured drug information"""
        drugs = []
        
        if not text:
            return drugs
        
        # Look for formulary table patterns
        table_patterns = [
            r'([A-Z][a-z\-\s]+)\s+(\d+(?:\.\d+)?\s*(?:mg|mcg|ml))\s+(\$?\d+(?:\.\d+)?)\s*(Tier\s*\d+)',
            r'([A-Z][a-z\-\s]+)\s+\|\s*([A-Z][a-z\-\s]+)\s+\|\s*(\d+(?:\.\d+)?\s*(?:mg|mcg))',
        ]
        
        for pattern in table_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                full_name = match.group(1).strip()
                # Extract drug name up until the first number appears
                drug_name = re.split(r'\s*\d', full_name)[0].strip() if full_name else ''
                drugs.append({
                    'name': drug_name,
                    'strength': match.group(2).strip() if len(match.groups()) > 1 else '',
                    'additional_info': ' | '.join(match.groups()[2:]) if len(match.groups()) > 2 else ''
                })
        
        return drugs
    
    def validate_medical_content(self, text: str, filename: str = "") -> bool:
        """Validate that the extracted text contains meaningful medical content"""
        if not text or len(text.strip()) < MEDICAL_CONFIG['min_content_length']:
            return False
        
        text_lower = text.lower()
        found_indicators = sum(1 for indicator in self.medical_indicators if indicator in text_lower)
        
        return found_indicators >= MEDICAL_CONFIG['min_medical_indicators']
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize extracted text for medical accuracy"""
        if not text:
            return ""
        
        # Remove excessive whitespaces while preserving structure
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Replace multiple newlines with double
        text = re.sub(r'[ \t]+', ' ', text)  # Replace multiple spaces/tabs with single space
        text = text.strip()
        
        # Ensure we preserve medical formatting (drug names, dosages, etc.)
        # Remove common PDF artifacts but keep medical information intact
        text = re.sub(r'\s*\|\s*', ' | ', text)  # Clean up table separators
        text = re.sub(r'\s*-\s*', ' - ', text)  # Clean up dashes
        
        return text
