import requests
import time

def test_search_latency(drug_name):
    url = "http://127.0.0.1:8000/api/v1/search"
    payload = {
        "drug_name": drug_name,
        "insurance_name": "UHC-001",
        "patient_context": {
            "conditions": ["Asthma"],
            "allergies": ["Penicillin"],
            "current_medications": [],
            "pregnancy_status": "not_pregnant",
            "alcohol_use": "no",
            "age_group": "adult"
        }
    }
    
    # First request
    print(f"--- Testing {drug_name} ---")
    start = time.time()
    res1 = requests.post(url, json=payload)
    end = time.time()
    print(f"First request (Uncached): {end - start:.4f} seconds")
    
    if res1.status_code != 200:
        print(f"Error: {res1.text}")
        return
        
    # Second request
    start2 = time.time()
    res2 = requests.post(url, json=payload)
    end2 = time.time()
    print(f"Second request (Cached): {end2 - start2:.4f} seconds")

if __name__ == "__main__":
    test_search_latency("Lisinopril")
