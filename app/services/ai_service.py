import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, List
import openai
from app.core.config import settings
from app.models.schemas import PatientContext, AIChatResponse, ChatResponse

logger = logging.getLogger(__name__)

CLINICAL_AI_SYSTEM_PROMPT = """You are Mediform AI, a clinical drug intelligence assistant. 
Your goal is to provide EXTREMELY CONCISE, precise, and accurate medical information.

CRITICAL RULES:
1. NO MARKDOWN SYMBOLS: Do not use hashtags (##), asterisks (** or *), or underscores (_).
2. NO FORMATTING: Provide the response in clean, plain text. Use simple dashes (-) for lists if needed.
3. BE BRIEF: Provide only the most essential information. Avoid lengthy descriptions.
4. SANITIZED OUTPUT: Ensure the output is ready to be displayed directly in a chat bubble without any parsing needed.
5. NO MEDICAL ADVICE: Include a short standard disclaimer to consult a professional at the very end.

Structure your response like this:
Drug Overview: [1-2 sentences]
Primary Use: [Essential use cases]
Dosage: [Key info only]
Warnings: [Most critical side effects/contraindications only]

If you don't know the answer, say "Information not available."
"""

class AiService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL_NAME

    async def get_chat_response(
        self, 
        query: str, 
        drug_data: Optional[Dict] = None, 
        coverage_data: Optional[Dict] = None,
        patient_context: Optional[PatientContext] = None
    ) -> Dict[str, Any]:
        """Non-streaming clinical AI response."""
        try:
            client = openai.OpenAI(api_key=self.api_key)
            context_str = self._build_context(query, drug_data, coverage_data, patient_context)
            
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[
                    {'role': 'system', 'content': CLINICAL_AI_SYSTEM_PROMPT},
                    {'role': 'user', 'content': context_str}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            return {
                "success": True,
                "response": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens
            }
        except Exception as e:
            logger.error(f"AiService.get_chat_response error: {e}")
            return {"success": False, "error": str(e)}

    async def stream_chat_response(
        self, 
        query: str, 
        drug_data: Optional[Dict] = None, 
        coverage_data: Optional[Dict] = None,
        patient_context: Optional[PatientContext] = None
    ) -> AsyncGenerator[str, None]:
        """Stream clinical AI response."""
        try:
            client = openai.OpenAI(api_key=self.api_key)
            context_str = self._build_context(query, drug_data, coverage_data, patient_context)
            
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[
                    {'role': 'system', 'content': CLINICAL_AI_SYSTEM_PROMPT},
                    {'role': 'user', 'content': context_str}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=1000
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"AiService.stream_chat_response error: {e}")
            yield f"Error: {str(e)}"

    async def perform_advanced_ai_search(
        self,
        query: str,
        patient_context: Optional[PatientContext],
        insurance_plan: Optional[str],
        rxnorm_service: Any,
        rag_service: Any
    ) -> ChatResponse:
        """
        Unified AI search pipeline combining query analysis, RxNorm data, 
        formulary info, and clinical logic.
        """
        client = openai.OpenAI(api_key=self.api_key)
        
        # 1. Identity drug names in query
        drug_analysis_prompt = f"Extract drug names and intent from clinical query: \"{query}\". Return JSON: {{'drug_names': [], 'intent': 'info|comparison|alternatives'}}"
        analysis_resp = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": drug_analysis_prompt}],
            response_format={"type": "json_object"}
        )
        analysis = json.loads(analysis_resp.choices[0].message.content)
        drug_names = analysis.get('drug_names', [])
        intent = analysis.get('intent', 'info')
        
        # 2. Gather data
        rxnorm_info = []
        for name in drug_names:
            rx = await rxnorm_service.get_drug_info(name)
            if rx: rxnorm_info.append(rx)
            
        formulary_info = []
        if insurance_plan:
            for name in drug_names:
                search_res = await rag_service.search_drug_alternatives(name, insurance_plan)
                if search_res.get('success'):
                    formulary_info.append({
                        'drug': name,
                        'plan': insurance_plan,
                        'status': search_res.get('primary_indication'),
                        'alternatives': search_res.get('alternatives', [])[:3]
                    })

        # 3. Generate response
        context = {
            'query': query,
            'patient': patient_context.dict() if patient_context else None,
            'rxnorm': rxnorm_info,
            'formulary': formulary_info
        }
        
        final_resp = await self.get_chat_response(query, drug_data=context, patient_context=patient_context)
        
        return ChatResponse(
            success=True,
            response=final_resp.get('response', ''),
            intent=intent,
            sources=["RxNorm API", f"{insurance_plan} Formulary" if insurance_plan else "General Clinical Data"],
            drug_info=rxnorm_info,
            formulary_info=formulary_info,
            tokens_used=final_resp.get('tokens_used', 0)
        )

    def _build_context(self, query: str, drug_data: Optional[Dict], coverage_data: Optional[Dict], patient_context: Optional[PatientContext] = None) -> str:
        parts = [f"User Query: {query}"]
        if patient_context:
            parts.append(f"Patient Context: {json.dumps(patient_context.dict())}")
        if drug_data:
            parts.append(f"Drug/Clinical Data: {json.dumps(drug_data)}")
        if coverage_data:
            parts.append(f"Coverage/Insurance Data: {json.dumps(coverage_data)}")
        return "\n".join(parts)

ai_service = AiService()
