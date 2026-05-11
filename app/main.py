import os
import logging
import asyncio
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.api.v1.router import api_router
from app.core.rate_limiter import limiter
from app.core.config import settings
from app.core.telemetry import init_telemetry
from app.services.database_service import DatabaseService
from app.services.rag_service import RagService, RagManager

from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def initialize_system():
    """Initialize system directories and databases at startup."""
    logger.info("Initializing Clinical Agent System...")
    
    # Ensure directories exist
    settings.ensure_directories()
    
    # Pre-load UnifiedDrugSystem (ML Models)
    try:
        from backend.services.safety_model_service import safety_service
        # Trigger lazy load
        safety_service.check_ddi_local(["ASPIRIN"])
        logger.info("Safety Models pre-loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to pre-load safety models: {e}")
    logger.info("System initialization complete.")

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="2.0.0",
        description="Production-grade Clinical Agent RAG Backend"
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return JSONResponse(
            status_code=429,
            content={"success": False, "detail": "Rate limit exceeded. Please try again later."}
        )

    # 1. Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Configure Sessions
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET_KEY,
        max_age=3600 * 24 * 7  # 7 days
    )

    # 3. Setup OpenTelemetry
    init_telemetry(app)

    # 3. Include API Routers
    # V1 structure
    app.include_router(api_router, prefix="/api/v1")
    # Base /api structure for backward compatibility
    app.include_router(api_router, prefix="/api")

    # 4. Global Startup Event
    @app.on_event("startup")
    async def startup_event():
        await initialize_system()

    # 5. Serve Static Frontend
    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        # Serve assets
        if (frontend_dist / "assets").exists():
            app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
        if (frontend_dist / "images").exists():
            app.mount("/images", StaticFiles(directory=str(frontend_dist / "images")), name="images")
        
        @app.get("/{rest_of_path:path}")
        async def serve_spa(rest_of_path: str):
            if rest_of_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "API Not Found"})
            
            file_path = frontend_dist / rest_of_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            
            index_path = frontend_dist / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            
            return JSONResponse(status_code=404, content={"detail": "Frontend not found"})
    else:
        logger.warning("Frontend dist directory not found. Static serving disabled.")

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
