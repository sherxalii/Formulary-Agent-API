from fastapi import APIRouter, Depends, Request
from typing import Dict, Any

from app.core.email_service import EmailService
from app.models.schemas import SystemInfo, CacheStatus, ContactRequest
from app.core.dependencies import get_rag_service, get_database_service
from app.services.rag_service import RagService
from app.services.database_service import DatabaseService

router = APIRouter()
email_service = EmailService()

@router.post("/contact")
async def contact_us(request: ContactRequest):
    """Handle contact us form submissions with auto-response."""
    # 1. Send notification to admin (simulated or real)
    admin_body = (
        f"New Contact Form Submission:\n\n"
        f"Name: {request.name}\n"
        f"Email: {request.email}\n"
        f"Subject: {request.subject}\n"
        f"Message: {request.message}"
    )
    # email_service.send_email("admin@mediformulary.com", f"Contact: {request.subject}", admin_body)

    # 2. Send auto-response to user
    user_body = (
        f"Hello {request.name},\n\n"
        f"Thank you for reaching out to us regarding '{request.subject}'.\n\n"
        "We have received your message and our team will respond to your problem shortly.\n\n"
        "Best regards,\n"
        "The MediFormulary Support Team"
    )
    email_service.send_email(request.email, "Support: We've received your message", user_body)

    return {"success": True, "message": "Your message has been sent. Check your email for confirmation."}


@router.get("/info", response_model=SystemInfo)
async def get_api_info(request: Request):
    """Provide information about the Clinical Agent RAG API."""
    # Logic to check user agent for monitoring probes could go here
    return SystemInfo()

@router.get("/test", tags=["Utility"])
async def test_endpoint():
    """Simple test endpoint to verify routes work."""
    return {"success": True, "message": "Clinical Agent API is operational."}

@router.get("/health", tags=["Utility"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@router.get("/cache-status", response_model=CacheStatus)
async def get_cache_status(
    rag_service: RagService = Depends(get_rag_service)
):
    """Get the current cache status of all RAG instances."""
    stats = rag_service.manager.get_cache_stats()
    return CacheStatus(
        cache_strategy="multiple_databases",
        total_cached_databases=len(stats),
        cached_databases=stats,
        preloaded=True
    )

@router.post("/clear-cache")
async def clear_cache(
    rag_service: RagService = Depends(get_rag_service)
):
    """Clear all in-memory RAG instance caches."""
    rag_service.manager.clear()
    return {"success": True, "message": "All RAG instance caches cleared."}

@router.get("/database-summary")
async def get_all_database_summaries(
    database_service: DatabaseService = Depends(get_database_service),
    rag_service: RagService = Depends(get_rag_service)
):
    """Get summaries for all available databases."""
    pdfs = await database_service.list_pdfs()
    summaries = {}
    for pdf in pdfs:
        db_id = pdf.replace(".pdf", "")
        summary = await rag_service.get_database_summary(db_id)
        summaries[db_id] = summary.get("summary")
    return {"success": True, "summaries": summaries}
