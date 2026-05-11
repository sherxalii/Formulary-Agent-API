from backend.formulary_drug_rag import FormularyDrugRAG
from app.core.config import settings
import os

def inspect_db(db_name):
    vectorstore_path = str(settings.DATABASE_DIR / db_name)
    rag = FormularyDrugRAG(
        openai_api_key=settings.OPENAI_API_KEY,
        chroma_persist_directory=vectorstore_path,
        enable_ai_enhancement=False
    )
    
    if not rag.load_existing_vectorstore():
        print(f"Failed to load {db_name}")
        return

    print(f"\n--- Inspecting {db_name} ---")
    print(f"Total ingredients: {len(rag.drug_database)}")
    
    search_term = "atorvastatin"
    found = False
    
    # Check keys
    if search_term in rag.drug_database:
        print(f"Found '{search_term}' as key!")
        found = True
        
    # Check all entries
    for ingredient, drugs in rag.drug_database.items():
        if search_term in ingredient.lower():
            print(f"Ingredient match: {ingredient}")
        for drug in drugs:
            if search_term in drug.get('drug_name', '').lower():
                print(f"Drug name match: {drug.get('drug_name')}")
            if search_term in drug.get('generic_name', '').lower():
                print(f"Generic name match: {drug.get('generic_name')}")

if __name__ == "__main__":
    inspect_db("2026_Drug_guide_Aetna_Standard_Plan")
