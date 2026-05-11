from fastapi import APIRouter
from app.api.v1.endpoints import search, ai, database, clinical, system, auth, dashboard

api_router = APIRouter()

# Keep paths flat under /api to match legacy Flask server where possible
api_router.include_router(search.router)
api_router.include_router(ai.router)
api_router.include_router(database.router)
api_router.include_router(clinical.router)
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
