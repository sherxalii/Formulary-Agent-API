from fastapi import APIRouter, Depends, HTTPException, Body, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import AIChatRequest, AIChatResponse, ChatResponse
from app.services.ai_service import AiService
from app.services.rxnorm_service import RxNormService
from app.services.rag_service import RagService
from app.core.dependencies import get_ai_service, get_rxnorm_service, get_rag_service
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/ai/chat", response_model=AIChatResponse)
async def chat_ai_response(
    request: AIChatRequest,
    ai_service: AiService = Depends(get_ai_service)
):
    """Non-streaming clinical AI response (fallback)."""
    result = await ai_service.get_chat_response(
        request.query,
        request.drugData,
        request.coverageData,
        request.patient_context
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return AIChatResponse(
        success=True,
        response=result.get("response"),
        intent=request.intent,
        tokens_used=result.get("tokens_used")
    )

@router.post("/ai/chat-stream")
async def stream_ai_response(
    request: AIChatRequest,
    ai_service: AiService = Depends(get_ai_service)
):
    """Stream clinical AI response with real-time token delivery."""
    return StreamingResponse(
        ai_service.stream_chat_response(
            request.query,
            request.drugData,
            request.coverageData,
            request.patient_context
        ),
        media_type="text/plain"
    )

@router.post("/ai-search", response_model=ChatResponse)
async def ai_search(
    request: Request,
    ai_service: AiService = Depends(get_ai_service),
    rxnorm_service: RxNormService = Depends(get_rxnorm_service),
    rag_service: RagService = Depends(get_rag_service)
):
    """Comprehensive AI search endpoint for drug information queries."""
    data = await request.json()
    query = data.get('query', '').strip()
    insurance_plan = data.get('insurance_plan', '')
    
    # We could also accept patient_id here and fetch it
    patient_context = data.get('patient_context')
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
        
    result = await ai_service.perform_advanced_ai_search(
        query=query,
        patient_context=patient_context,
        insurance_plan=insurance_plan,
        rxnorm_service=rxnorm_service,
        rag_service=rag_service
    )
    
    return result
