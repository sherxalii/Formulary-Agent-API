import requests
import time
import json

URL = "http://localhost:8000/api/v1/personalized-check"
PAYLOAD = {
    "drugs": ["ASPIRIN", "WARFARIN", "METFORMIN"],
    "patient_context": {
        "conditions": ["hypertension"],
        "allergies": [],
        "pregnancy_status": "not_pregnant",
        "alcohol_use": "none",
        "age_group": "adult"
    }
}

def test_performance(iteration):
    print(f"\n--- Iteration {iteration} ---")
    start_time = time.time()
    try:
        response = requests.post(URL, json=PAYLOAD)
        duration = time.time() - start_time
        if response.status_code == 200:
            print(f"Success! Time taken: {duration:.2f} seconds")
            # print(json.dumps(response.json(), indent=2))
        else:
            print(f"Failed with status {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing DDI Performance Optimization...")
    # First run (should be faster than before due to parallelization, but still takes ~2s for OpenAI)
    test_performance(1)
    
    # Second run (should be near-instant due to caching)
    test_performance(2)
