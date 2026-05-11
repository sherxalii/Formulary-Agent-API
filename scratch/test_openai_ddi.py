from app.services.rxnorm_service import RxNormService
import asyncio

async def test():
    service = RxNormService()
    drugs = ["Voquezna 14 Day TriplePak 20;500;500 (Amoxicillin 500mg / Clarithromycin 500mg / Vonoprazan 20mg) Oral Tablet", "Millipred (Prednisolone 5mg) Oral Tablet"]
    res = await service.get_interactions(drugs)
    print("Interactions:", res)

if __name__ == "__main__":
    asyncio.run(test())
