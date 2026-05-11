"""
Local DDI model smoke-test.
Run from project root: python Model_Training/test_local_ddi.py
"""
import asyncio
import os
import sys
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.clinical_service import ClinicalService
from backend.services.safety_model_service import _get_unified


async def test_local_ddi():
    service = ClinicalService()
    unified = _get_unified()

    if unified is None or not unified.drug_profiles:
        print("[FAIL] UnifiedDrugSystem not loaded or no drug profiles available.")
        return

    profile_drugs = list(unified.drug_profiles.keys())
    print(f"Profiles available: {len(profile_drugs)}")

    # Try to find a known-interacting pair in the first 50 profiles
    drugs = random.sample(profile_drugs, min(2, len(profile_drugs)))
    found = False
    for d1 in profile_drugs[:50]:
        for d2 in profile_drugs[:50]:
            if d1 != d2:
                alerts = await service.check_ddi_local([d1, d2])
                if alerts:
                    drugs = [d1, d2]
                    found = True
                    break
        if found:
            break

    print(f"\nTesting DDI for: {drugs}")
    alerts = await service.check_ddi_local(drugs)

    if alerts:
        print("[SUCCESS] Interactions found:")
        for alert in alerts:
            print(f"  - {alert.severity.upper()}: {alert.message[:120]}")
    else:
        print("[INFO] No interactions detected for this pair.")

    for d in drugs:
        in_profile = d.upper() in unified.drug_profiles
        print(f"  Drug '{d}' in profiles: {in_profile}")


if __name__ == "__main__":
    asyncio.run(test_local_ddi())
