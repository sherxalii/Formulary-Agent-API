import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_search(drug_name, insurance_name, patient_context=None):
    url = f"{BASE_URL}/search"
    payload = {
        "drug_name": drug_name,
        "insurance_name": insurance_name,
        "patient_context": patient_context
    }
    
    print(f"\n--- Testing search for '{drug_name}' with insurance '{insurance_name}' ---")
    if patient_context:
        print(f"Patient Context: {patient_context}")
    
    start = time.time()
    try:
        response = requests.post(url, json=payload)
        end = time.time()
        
        print(f"Response time: {end - start:.2f}s")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Primary Indication: {data.get('primary_indication')}")
            print(f"Number of alternatives: {len(data.get('alternatives', []))}")
            if data.get('is_exact_match'):
                print("Exact match found!")
            
            # Print first alternative if any
            if data.get('alternatives'):
                alt = data['alternatives'][0]
                # Note: alt might be a dict or an object depending on schema
                name = alt.get('drug_name') if isinstance(alt, dict) else alt.get('drug_name', 'N/A')
                print(f"Top alternative: {name}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    # Test 1: Covered drug without context (should be fast/exact)
    test_search("Atorvastatin", "2026_Drug_guide_Aetna_Standard_Plan")
    
    # Test 2: Covered drug with context (should find alternatives)
    test_search("Atorvastatin", "2026_Drug_guide_Aetna_Standard_Plan", {
        "conditions": ["asthma"],
        "allergies": ["itching"],
        "age_group": "adult"
    })
    
    # Test 3: Non-covered drug
    test_search("Ozempic", "2026_Drug_guide_Aetna_Standard_Plan")
