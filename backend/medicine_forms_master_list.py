class MedicineFormsMaster:
    """Master class containing comprehensive medicine forms categorized by type."""
    
    # Basic dosage forms
    BASIC_FORMS = [
        'tablet', 'capsule', 'pill', 'caplet', 'lozenge', 'wafer',
        'solution', 'liquid', 'syrup', 'elixir', 'suspension', 'emulsion',
        'injection', 'infusion', 'vaccine', 'serum',
        'cream', 'ointment', 'gel', 'lotion', 'paste', 'foam',
        'patch', 'disc', 'film', 'strip', 'bandage',
        'spray', 'mist', 'aerosol', 'inhaler', 'nebulizer',
        'drops', 'oil', 'tincture', 'extract',
        'powder', 'granules', 'pellets',
        'suppository', 'enema', 'douche',
        'implant', 'device', 'ring', 'coil',
        'chewable tablet', 'sublingual tablet', 'effervescent tablet'
    ]
    
    # Route-specific forms
    ORAL_FORMS = [ 
        'oral tablet', 'oral capsule', 'oral solution', 'oral suspension',
        'oral concentrate', 'oral powder', 'oral granules', 'oral film',
        'oral strip', 'oral drops', 'oral syrup', 'oral elixir',
        'chewable tablet', 'dispersible tablet', 'effervescent tablet',
        'sublingual tablet', 'buccal tablet', 'orally disintegrating tablet',
        'mouth rinse', 'mouthwash', 'throat solution', 'oral spray', 'oral lozenge'
    ]
    
    TOPICAL_FORMS = [
        'topical cream', 'topical ointment', 'topical gel', 'topical lotion',
        'topical solution', 'topical spray', 'topical foam', 'topical patch',
        'external cream', 'external ointment', 'external gel', 'external lotion',
        'external solution', 'external patch', 'external foam',
        'dermal patch', 'skin patch', 'topical roll-on', 'topical mousse','shampoo'
    ]
    
    INJECTION_FORMS = [
        'subcutaneous injection', 'intramuscular injection', 'intravenous injection',
        'intradermal injection', 'intrathecal injection', 'epidural injection',
        'intraarticular injection', 'intravitreal injection',
        'prefilled syringe', 'pen injector', 'auto-injector',
        'cartridge', 'vial', 'ampoule', 'infusion bag', 'IV drip', 'IV push',
        'vaccine syringe', 'biological injection'
    ]
    
    INHALATION_FORMS = [
        'metered dose inhaler', 'dry powder inhaler', 'nebulizer solution',
        'inhalation aerosol', 'inhalation powder', 'inhalation solution',
        'breath activated', 'diskus', 'turbuhaler', 'rotahaler', 'oral inhalation',
        'nasal inhalation', 'inhalation powder', 'bronchodilator aerosol'
    ]
    
    NASAL_FORMS = [
        'nasal spray', 'nasal drops', 'nasal gel', 'nasal ointment',
        'nasal solution', 'nasal powder', 'nasal mist', 'nasal inhaler',
        'intranasal aerosol'
    ]
    
    OPHTHALMIC_FORMS = [
        'eye drops', 'eye ointment', 'eye gel', 'eye solution',
        'ophthalmic drops', 'ophthalmic ointment', 'ophthalmic gel',
        'ophthalmic solution', 'ophthalmic suspension', 'eye patch'
    ]
    
    OTIC_FORMS = [
        'ear drops', 'ear solution', 'ear suspension',
        'otic drops', 'otic solution', 'otic suspension', 'ear gel'
    ]
    
    RECTAL_FORMS = [
        'rectal suppository', 'rectal cream', 'rectal ointment',
        'rectal solution', 'rectal foam', 'enema', 'rectal gel'
    ]
    
    VAGINAL_FORMS = [
        'vaginal suppository', 'vaginal cream', 'vaginal gel',
        'vaginal tablet', 'vaginal ring', 'vaginal foam',
        'vaginal solution', 'vaginal douche', 'vaginal patch', 'vaginal implant'
    ]
    
    # Release mechanism forms
    RELEASE_FORMS = [
        'immediate release', 'extended release', 'sustained release',
        'delayed release', 'controlled release', 'modified release',
        'enteric coated', 'film coated', 'sugar coated', 'slow-release',
        'rapid release', 'fast-dissolving'
    ]
    
    # Special formulations
    SPECIAL_FORMS = [
        'liposomal', 'microsphere', 'nanoparticle', 'emulsion',
        'complex', 'conjugate', 'prodrug', 'biosimilar', 'gene therapy',
        'RNA-based', 'vaccine', 'peptide-based'
    ]
    
    # Combination identifiers
    COMBINATION_INDICATORS = [
        'fixed dose combination', 'combination', 'plus', 'with', 'and',
        'dual combination', 'triple combination', 'quadruple combination'
    ]
    
    # Generic descriptors
    GENERIC_DESCRIPTORS = [
        # 'various', 'multiple', 'all forms', 'different strengths',
        # 'assorted', 'mixed', 'unspecified', 'combination form'
    ]

    @classmethod
    def get_all_forms(cls) -> list:
        """Get all medicine forms as a single comprehensive list."""
        all_forms = []
        
        # Combine all form categories
        form_categories = [
            cls.BASIC_FORMS, cls.ORAL_FORMS, cls.TOPICAL_FORMS,
            cls.INJECTION_FORMS, cls.INHALATION_FORMS, cls.NASAL_FORMS,
            cls.OPHTHALMIC_FORMS, cls.OTIC_FORMS, cls.RECTAL_FORMS,
            cls.VAGINAL_FORMS, cls.RELEASE_FORMS, cls.SPECIAL_FORMS,
            cls.GENERIC_DESCRIPTORS
        ]
        
        for category in form_categories:
            all_forms.extend(category)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_forms = []
        for form in all_forms:
            if form not in seen:
                seen.add(form)
                unique_forms.append(form)
        
        return unique_forms
    
    @classmethod
    def get_forms_by_category(cls) -> dict:
        """Get forms organized by category."""
        return {
            'basic': cls.BASIC_FORMS,
            'oral': cls.ORAL_FORMS,
            'topical': cls.TOPICAL_FORMS,
            'injection': cls.INJECTION_FORMS,
            'inhalation': cls.INHALATION_FORMS,
            'nasal': cls.NASAL_FORMS,
            'ophthalmic': cls.OPHTHALMIC_FORMS,
            'otic': cls.OTIC_FORMS,
            'rectal': cls.RECTAL_FORMS,
            'vaginal': cls.VAGINAL_FORMS,
            'release': cls.RELEASE_FORMS,
            'special': cls.SPECIAL_FORMS,
            'generic': cls.GENERIC_DESCRIPTORS
        }
    
    @classmethod
    def categorize_form(cls, form_text: str) -> str:
        """Categorize a medicine form into its primary category."""
        form_lower = form_text.lower().strip()
        
        categories = cls.get_forms_by_category()
        
        for category_name, forms in categories.items():
            for form in forms:
                if form in form_lower or form_lower in form:
                    return category_name
        
        return 'unknown'
    
    @classmethod
    def find_best_match(cls, text: str, threshold: float = 0.8) -> str:
        """Find the best matching medicine form from the master list."""
        import difflib
        
        text_lower = text.lower().strip()
        all_forms = cls.get_all_forms()
        
        # Try exact match first
        if text_lower in all_forms:
            return text_lower
        
        # Try fuzzy matching
        close_matches = difflib.get_close_matches(
            text_lower, all_forms, n=1, cutoff=threshold
        )
        
        if close_matches:
            return close_matches[0]
        
        # Try partial matching
        for form in all_forms:
            if form in text_lower or text_lower in form:
                return form
        
        return text_lower  # Return original if no match found
    
    @classmethod
    def extract_forms_from_text(cls, text: str) -> list:
        """Extract all medicine forms found in a text string."""
        found_forms = []
        text_lower = text.lower()
        all_forms = cls.get_all_forms()
        
        # Sort by length (longest first) to catch compound forms first
        sorted_forms = sorted(all_forms, key=len, reverse=True)
        
        for form in sorted_forms:
            if form in text_lower:
                found_forms.append(form)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(found_forms))


# Example usage and testing
if __name__ == "__main__":
    master = MedicineFormsMaster()
    
    # Test categorization
    print("Testing categorization:")
    test_forms = [
        "Oral Tablet",
        "Subcutaneous Injection", 
        "Topical Cream",
        "Eye Drops",
        "Extended Release",
        "Liposomal Formulation",
        "Peptide-based Vaccine"
    ]
    
    for form in test_forms:
        category = master.categorize_form(form)
        print(f"  {form} -> {category}")
    
    # Test extraction
    print("\nTesting extraction:")
    sample_text = "Metformin (Oral Tablet Immediate Release) and Insulin (Subcutaneous Injection)"
    found = master.extract_forms_from_text(sample_text)
    print(f"  Found forms: {found}")
    
    # Show total count
    all_forms = master.get_all_forms()
    print(f"\nTotal medicine forms in master list: {len(all_forms)}")
