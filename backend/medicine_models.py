"""
Pydantic models for medicine data validation and LLM structured outputs.
Compatible with Pydantic v2 - ensures robust data quality and eliminates "None" values.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal
import re


class MedicineEntry(BaseModel):
    """
    Pydantic model for medicine entries with comprehensive validation.
    Ensures no "None" values and proper data formatting.
    Can be used as LLM response format for structured outputs.
    """
    
    drug_name: str = Field(..., min_length=2, description="Clean drug name without form (e.g., 'Metformin HCl')")
    generic_name: str = Field(..., min_length=2, description="Generic/active ingredient name (e.g., 'metformin')")
    medicine_form: str = Field(..., description="medicine form")
    active_ingredient: str = Field(..., min_length=2, description="Active ingredient (usually same as generic_name)")
    therapeutic_class: str = Field(
        default="Unknown", 
        description="**HIGH PRIORITY** Therapeutic class/category (e.g., 'Antifungal', 'Antidiabetic', 'Antihypertensive', 'Antibiotic')"
    )
    tier: str = Field(default="Unknown", description="Formulary tier (e.g., 'Tier 1', 'Tier 2', etc.)")
    restrictions: str = Field(default="None", description="Coverage restrictions (e.g., 'PA', 'ST', 'QL', etc.)")
    strength: str = Field(..., description="Medicine strength (e.g., '500mg', '10ml', etc.)")
    
    # Enhanced fields for complete medicine database
    alternative_names: str = Field(default="", description="Alternative names, brands, or synonyms for this medicine")
    
    # Optional fields for internal use
    dosage_form: Optional[str] = Field(default=None, description="Alias for medicine_form")
    source_document: Optional[str] = Field(default="", description="Source document name")
    confidence: Optional[float] = Field(default=0.8, ge=0.0, le=1.0, description="Extraction confidence")
    
    class Config:
        # Use enum values for validation
        validate_assignment = True
        # JSON schema for OpenAI structured outputs
        json_schema_extra = {
            "description": "Medicine entry with validated fields - no None/unknown values allowed",
            "examples": [
                {
                    "drug_name": "Ciclopirox",
                    "generic_name": "ciclopirox",
                    "medicine_form": "Topical",
                    "active_ingredient": "ciclopirox",
                    "therapeutic_class": "Antifungal",
                    "tier": "QL (120/28)",
                    "restrictions": "QL",
                    "strength": " ",
                    "alternative_names": "ciclopirox, topical shampoo"
                },
                {
                    "drug_name": "Metformin HCl",
                    "generic_name": "metformin",
                    "medicine_form": "Not Specified",
                    "active_ingredient": "metformin",
                    "therapeutic_class": "Antidiabetic",
                    "tier": "Tier 1",
                    "restrictions": "None",
                    "strength": "500mg",
                    "alternative_names": "metformin, diabetes medication"
                }
            ]
        }
    
    @field_validator('drug_name', mode='before')
    @classmethod
    def clean_drug_name(cls, v):
        """Clean and validate drug name."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            raise ValueError("Drug name cannot be empty or 'None'")
        
        # Clean the drug name
        cleaned = str(v).strip()
        
        # Remove common problematic patterns
        cleaned = re.sub(r'\b(same|unknown|unclear|not specified)\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        if len(cleaned) < 2:
            raise ValueError(f"Drug name too short after cleaning: '{cleaned}'")
            
        return cleaned
    
    @field_validator('generic_name', mode='before')
    @classmethod
    def clean_generic_name(cls, v, info):
        """Clean and validate generic name with smart fallbacks."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            # Use drug_name as fallback for generic_name if available
            if hasattr(info, 'data') and 'drug_name' in info.data:
                drug_name = info.data['drug_name']
                if drug_name:
                    return cls._extract_generic_from_drug_name(drug_name)
            raise ValueError("Generic name cannot be empty and no valid drug_name for fallback")
        
        cleaned = str(v).strip().lower()
        
        # Clean problematic values
        if cleaned in ['same', 'unknown', 'unclear', 'not specified']:
            if hasattr(info, 'data') and 'drug_name' in info.data:
                drug_name = info.data['drug_name']
                if drug_name:
                    return cls._extract_generic_from_drug_name(drug_name)
            raise ValueError("Invalid generic name and no drug_name for fallback")
        
        return cleaned
    
    @field_validator('active_ingredient', mode='before')
    @classmethod
    def clean_active_ingredient(cls, v, info):
        """Clean active ingredient with fallback to generic_name."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            # Use generic_name as fallback
            if hasattr(info, 'data') and 'generic_name' in info.data:
                generic_name = info.data['generic_name']
                if generic_name:
                    return generic_name.lower()
            
            # Use drug_name as last resort
            if hasattr(info, 'data') and 'drug_name' in info.data:
                drug_name = info.data['drug_name']
                if drug_name:
                    return cls._extract_generic_from_drug_name(drug_name).lower()
            
            raise ValueError("Active ingredient cannot be empty")
        
        return str(v).strip().lower()
    
    @field_validator('medicine_form', mode='before')
    @classmethod
    def clean_medicine_form(cls, v):
        """Clean and validate medicine form with comprehensive fallbacks."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            return "Not Specified"  # Safe default
        
        cleaned = str(v).strip()
        
        # Handle problematic values
        if cleaned.lower() in ['same', 'unknown', 'unclear', 'not specified', 'none']:
            return "Not Specified"  # Safe default
        generic_descriptors = {'various','multiple','all forms','different strengths','assorted','mixed','unspecified','combination form'}
        if cleaned.lower() in generic_descriptors:
            return "Unknown"    
        # Try to standardize common forms to our Literal values
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
            'lotion': 'Lotion', 'powder': 'Powder','shampoo': 'Shampoo',
        }
        
        cleaned_lower = cleaned.lower().strip()
        if cleaned_lower in form_mapping:
            return form_mapping[cleaned_lower]
        
        # Check if it contains any of our valid forms
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
    
    @field_validator('therapeutic_class', mode='before')
    @classmethod
    def clean_therapeutic_class(cls, v, info):
        """Clean and intelligently extract therapeutic class with drug name inference."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            # Try to infer therapeutic class from drug/generic name
            drug_name = ""
            generic_name = ""
            
            if hasattr(info, 'data'):
                drug_name = info.data.get('drug_name', '').lower()
                generic_name = info.data.get('generic_name', '').lower()
            
            # Comprehensive therapeutic class inference based on drug names
            inferred_class = cls._infer_therapeutic_class(drug_name, generic_name)
            return inferred_class if inferred_class != "Unknown" else "Unknown"
        
        cleaned = str(v).strip()
        
        # If it's a problematic value, try inference
        if cleaned.lower() in ['same', 'unknown', 'unclear', 'not specified', 'none']:
            drug_name = ""
            generic_name = ""
            
            if hasattr(info, 'data'):
                drug_name = info.data.get('drug_name', '').lower()
                generic_name = info.data.get('generic_name', '').lower()
            
            inferred_class = cls._infer_therapeutic_class(drug_name, generic_name)
            return inferred_class if inferred_class != "Unknown" else "Unknown"
        
        return cleaned
    
    @field_validator('tier', mode='before')
    @classmethod
    def clean_tier(cls, v):
        """Clean tier information."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            return "Unknown"
        return str(v).strip()
    
    @field_validator('restrictions', mode='before')
    @classmethod
    def clean_restrictions(cls, v):
        """Clean restrictions."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            return "None"
        return str(v).strip()
    
    @field_validator('strength', mode='before')
    @classmethod
    def clean_strength(cls, v):
        """Clean strength information."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            return "Unknown"
        
        cleaned = str(v).strip()
        # Check if it contains numbers (valid strength)
        if re.search(r'\d', cleaned):
            return cleaned
        else:
            return "Unknown"
    
    @field_validator('alternative_names', mode='before')
    @classmethod
    def clean_alternative_names(cls, v, info):
        """Generate alternative names including generic, drug name, and common variants."""
        if not v or isinstance(v, str) and v.strip().lower() in ['none', 'unknown', 'same', 'unclear', '', 'n/a']:
            # Auto-generate alternative names from drug_name and generic_name
            alternatives = []
            
            if hasattr(info, 'data'):
                drug_name = info.data.get('drug_name', '').strip()
                generic_name = info.data.get('generic_name', '').strip()
                medicine_form = info.data.get('medicine_form', '').strip()
                
                if drug_name:
                    alternatives.append(drug_name.lower())
                if generic_name and generic_name.lower() != drug_name.lower():
                    alternatives.append(generic_name.lower())
                if medicine_form and medicine_form.lower() not in ['not specified', 'unknown']:
                    alternatives.append(medicine_form.lower())
                
                # Remove duplicates and join
                unique_alternatives = list(dict.fromkeys(alternatives))  # Preserves order
                return ", ".join(unique_alternatives) if unique_alternatives else ""
            
            return ""
        
        return str(v).strip()
    
    @model_validator(mode='after')
    def sync_dosage_form_and_infer_missing(self):
        """Ensure dosage_form matches medicine_form and infer missing therapeutic class."""
        # Sync dosage form
        if self.dosage_form is None:
            self.dosage_form = self.medicine_form
        
        # Infer therapeutic class if it's still Unknown
        if self.therapeutic_class == "Unknown":
            inferred_class = self._infer_therapeutic_class(self.drug_name, self.generic_name)
            if inferred_class != "Unknown":
                self.therapeutic_class = inferred_class
        
        # Generate alternative names if empty
        if not self.alternative_names:
            alternatives = []
            if self.drug_name:
                alternatives.append(self.drug_name.lower())
            if self.generic_name and self.generic_name.lower() != self.drug_name.lower():
                alternatives.append(self.generic_name.lower())
            if self.medicine_form and self.medicine_form.lower() not in ['not specified', 'unknown']:
                alternatives.append(self.medicine_form.lower())
            
            # Remove duplicates and join
            unique_alternatives = list(dict.fromkeys(alternatives))
            self.alternative_names = ", ".join(unique_alternatives) if unique_alternatives else ""
        
        return self
    
    @staticmethod
    def _extract_generic_from_drug_name(drug_name: str) -> str:
        """Extract likely generic name from drug name."""
        if not drug_name:
            return "unknown"
        
        cleaned = drug_name.lower().strip()
        
        # Remove common brand indicators and suffixes
        cleaned = re.sub(r'\b(brand|®|™|cr|xl|er|sr|la|cd|od|xr|hcl|hydrochloride|sulfate|tartrate|sodium|potassium)\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # If nothing left, use original
        return cleaned if cleaned and len(cleaned) > 1 else drug_name.lower()
    
    @staticmethod
    def _infer_therapeutic_class(drug_name: str, generic_name: str) -> str:
        """
        🎯 COMPREHENSIVE therapeutic class inference from drug/generic names.
        This is CRITICAL for your database - matches your priority requirement!
        """
        # Combine both names for comprehensive matching
        combined_text = f"{drug_name} {generic_name}".lower()
        
        # Comprehensive therapeutic class mappings based on drug name patterns
        therapeutic_mappings = {
            # 🩺 Diabetes & Metabolic
            "antidiabetic": ["metformin", "ozempic", "wegovy", "trulicity", "jardiance", "farxiga", "januvia", "glipizide", "glyburide", "insulin", "semaglutide", "liraglutide", "dulaglutide", "empagliflozin", "dapagliflozin", "sitagliptin"],
            
            # 🫀 Cardiovascular
            "antihypertensive": ["lisinopril", "losartan", "amlodipine", "atenolol", "metoprolol", "hydrochlorothiazide", "valsartan", "enalapril", "ramipril", "carvedilol", "bisoprolol"],
            "antilipemic": ["atorvastatin", "simvastatin", "rosuvastatin", "lipitor", "crestor", "pravastatin", "lovastatin", "fluvastatin"],
            "anticoagulant": ["warfarin", "coumadin", "eliquis", "xarelto", "pradaxa", "apixaban", "rivaroxaban", "dabigatran"],
            
            # 🧠 Neurological & Psychiatric
            "antidepressant": ["sertraline", "fluoxetine", "citalopram", "escitalopram", "zoloft", "prozac", "lexapro", "duloxetine", "venlafaxine", "bupropion", "trazodone"],
            "antianxiety": ["alprazolam", "lorazepam", "clonazepam", "xanax", "ativan", "klonopin", "diazepam", "valium"],
            "anticonvulsant": ["gabapentin", "pregabalin", "phenytoin", "carbamazepine", "valproic acid", "lamotrigine", "levetiracetam"],
            "antiparkinson": ["levodopa", "carbidopa", "sinemet", "pramipexole", "ropinirole", "rasagiline"],
            
            # 🦠 Anti-infective
            "antibiotic": ["amoxicillin", "azithromycin", "ciprofloxacin", "doxycycline", "cephalexin", "clindamycin", "metronidazole", "trimethoprim", "sulfamethoxazole", "penicillin", "ceftriaxone"],
            "antiviral": ["acyclovir", "valacyclovir", "oseltamivir", "tamiflu", "remdesivir", "paxlovid"],
            "antifungal": ["fluconazole", "itraconazole", "terbinafine", "ciclopirox", "ketoconazole", "clotrimazole", "miconazole"],
            
            # 🫁 Respiratory
            "bronchodilator": ["albuterol", "salbutamol", "ipratropium", "tiotropium", "formoterol", "salmeterol"],
            "inhaled corticosteroid": ["fluticasone", "budesonide", "beclomethasone", "mometasone", "ciclesonide"],
            "antihistamine": ["loratadine", "cetirizine", "fexofenadine", "diphenhydramine", "chlorpheniramine", "zyrtec", "claritin", "allegra"],
            
            # 🩹 Pain & Inflammation
            "analgesic": ["acetaminophen", "ibuprofen", "naproxen", "tramadol", "oxycodone", "hydrocodone", "morphine", "codeine", "tylenol", "advil", "motrin"],
            "nsaid": ["ibuprofen", "naproxen", "diclofenac", "celecoxib", "indomethacin", "meloxicam"],
            "muscle relaxant": ["cyclobenzaprine", "baclofen", "tizanidine", "methocarbamol", "carisoprodol"],
            
            # 🔥 Gastrointestinal
            "proton pump inhibitor": ["omeprazole", "esomeprazole", "lansoprazole", "pantoprazole", "rabeprazole", "nexium", "prilosec", "prevacid"],
            "h2 antagonist": ["famotidine", "ranitidine", "cimetidine", "nizatidine", "pepcid", "zantac"],
            "antidiarrheal": ["loperamide", "bismuth", "imodium", "pepto"],
            "laxative": ["docusate", "senna", "polyethylene glycol", "miralax", "dulcolax"],
            
            # 🦴 Bone & Joint
            "bisphosphonate": ["alendronate", "risedronate", "ibandronate", "zoledronic", "fosamax", "actonel", "boniva"],
            "antigout": ["allopurinol", "colchicine", "febuxostat", "probenecid"],
            
            # 🧴 Dermatological
            "topical corticosteroid": ["hydrocortisone", "triamcinolone", "betamethasone", "clobetasol", "fluocinonide"],
            "topical antibiotic": ["mupirocin", "bacitracin", "neomycin", "polymyxin"],
            "topical antifungal": ["ciclopirox", "terbinafine", "clotrimazole", "miconazole", "ketoconazole"],
            
            # 👁️ Ophthalmologic
            "ophthalmic antibiotic": ["ciprofloxacin ophthalmic", "tobramycin ophthalmic", "erythromycin ophthalmic"],
            "ophthalmic steroid": ["prednisolone ophthalmic", "dexamethasone ophthalmic"],
            
            # 🌸 Hormonal
            "thyroid hormone": ["levothyroxine", "liothyronine", "synthroid", "cytomel"],
            "corticosteroid": ["prednisone", "prednisolone", "methylprednisolone", "dexamethasone", "hydrocortisone"],
            "hormone replacement": ["estradiol", "progesterone", "testosterone", "premarin"],
            
            # 🧠 Cognitive/Dementia
            "cholinesterase inhibitor": ["donepezil", "rivastigmine", "galantamine", "aricept", "exelon", "razadyne"],
            
            # 🩸 Hematologic
            "antiplatelet": ["clopidogrel", "aspirin", "prasugrel", "ticagrelor", "plavix"],
            "iron supplement": ["ferrous sulfate", "ferrous gluconate", "iron", "feosol"],
            
            # 💊 Urological
            "alpha blocker": ["tamsulosin", "doxazosin", "terazosin", "alfuzosin", "flomax"],
            "5-alpha reductase inhibitor": ["finasteride", "dutasteride", "propecia", "proscar"],
        }
        
        # Search for matches in the combined text
        for therapeutic_class, drug_patterns in therapeutic_mappings.items():
            for pattern in drug_patterns:
                if pattern in combined_text:
                    return therapeutic_class.title()  # Return with proper capitalization
        
        # Special pattern matching for complex names
        if any(keyword in combined_text for keyword in ["shampoo", "topical"]):
            if any(antifungal in combined_text for antifungal in ["ciclopirox", "ketoconazole", "selenium"]):
                return "Antifungal"
            else:
                return "Topical"
        
        if "pen" in combined_text and any(diabetes in combined_text for diabetes in ["insulin", "ozempic", "wegovy", "trulicity"]):
            return "Antidiabetic"
        
        if "inhaler" in combined_text or "nebulizer" in combined_text:
            return "Bronchodilator"
        
        if "injection" in combined_text:
            if any(diabetes in combined_text for diabetes in ["insulin", "ozempic", "wegovy", "trulicity"]):
                return "Antidiabetic"
            elif any(pain in combined_text for pain in ["steroid", "cortisone"]):
                return "Corticosteroid"
        
        # Return Unknown if no match found
        return "Unknown"


class MedicineExtractionResponse(BaseModel):
    """
    Response format for LLM medicine extraction with structured outputs.
    This is the format that OpenAI will be forced to return.
    """
    
    medicines: List[MedicineEntry] = Field(default_factory=list, description="List of extracted medicines")
    extraction_metadata: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_found": 0,
            "extraction_method": "llm_structured_output",
            "confidence": 0.9
        },
        description="Metadata about the extraction process"
    )
    
    @model_validator(mode='after')
    def update_metadata(self):
        """Update metadata based on extracted medicines."""
        self.extraction_metadata['total_found'] = len(self.medicines)
        return self
    
    class Config:
        json_schema_extra = {
            "description": "Structured response for medicine extraction from formulary text",
            "examples": [
                {
                    "medicines": [
                        {
                            "drug_name": "Ciclopirox",
                            "generic_name": "ciclopirox",
                            "medicine_form": "Topical",
                            "active_ingredient": "ciclopirox",
                            "therapeutic_class": "Antifungal",
                            "tier": "QL (120/28)",
                            "restrictions": "QL",
                            "strength": "1%",
                            "alternative_names": "ciclopirox, topical shampoo"
                        }
                    ],
                    "extraction_metadata": {
                        "total_found": 1,
                        "extraction_method": "llm_structured_output",
                        "confidence": 0.9
                    }
                }
            ]
        }


class MedicineList(BaseModel):
    """Container for multiple medicine entries with validation."""
    
    medicines: List[MedicineEntry] = Field(default_factory=list)
    source_document: str = Field(default="")
    extraction_method: str = Field(default="llm")
    total_count: int = Field(default=0)
    
    @model_validator(mode='after')
    def update_count(self):
        """Update total count based on medicines list."""
        self.total_count = len(self.medicines)
        return self
    
    def add_medicine(self, medicine_data: Dict[str, Any]) -> bool:
        """Add a medicine with validation."""
        try:
            medicine = MedicineEntry(**medicine_data)
            self.medicines.append(medicine)
            self.total_count = len(self.medicines)
            return True
        except Exception as e:
            print(f"⚠️ Failed to validate medicine: {e}")
            return False
    
    def get_valid_medicines(self) -> List[Dict[str, Any]]:
        """Get all medicines as dictionaries."""
        return [medicine.model_dump() for medicine in self.medicines]
    
    def filter_by_form(self, form: str) -> List[MedicineEntry]:
        """Filter medicines by form."""
        return [med for med in self.medicines if med.medicine_form.lower() == form.lower()]
    
    def get_unique_forms(self) -> List[str]:
        """Get unique medicine forms."""
        return list(set(med.medicine_form for med in self.medicines))
