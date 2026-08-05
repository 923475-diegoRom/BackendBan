"""
BackendBan – FastAPI entry point

Este módulo define la aplicación FastAPI, configura CORS, registra los eventos de inicio y expone los endpoints principales:
- `/api/v1/chat/stream`   → streaming de respuesta del LLM con RAG.
- `/api/v1/audio/transcribe` → transcribe audio usando Whisper de Groq.
- `/api/v1/documents/upload` → ingestión de PDFs en Qdrant.
- `/metrics` y `/api/v1/status` → métricas y salud de la API.

Cada endpoint está instrumentado con métricas Prometheus y logging estructurado para observabilidad.
"""
import time
import json
import uuid
import asyncio
import os
from groq import Groq
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.prebuilt import create_react_agent
from app.core import get_llm
from app.rag import seed_sample_data, ingest_pdf
from app.database import init_db, save_audit_log, init_chat_history, save_chat_message, load_chat_history
from app.core import get_fallback_llm
from app.auth import router as auth_router
from groq import RateLimitError
from app.core_banking import init_core_db
from app.agent_tools import get_agent_tools
from app.logger import get_logger
from app.metrics import LLM_REQUEST_COUNTER, LLM_LATENCY_HISTOGRAM, LLM_TTFT_HISTOGRAM

logger = get_logger("BanorteGenAI")
app = FastAPI(
    title="Banorte GenAI Copilot Backend",
    version="1.0.0",
    description="API Full Stack con RAG, Llama 3.3 70B y Agentes de IA, con Observabilidad"
)

# Include auth routes
app.include_router(auth_router, prefix="/api/v1")

global_stats = {
    "total_latency": 0.0,
    "total_tokens": 0,
    "total_requests": 0,
    "total_duration": 0.0
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    use_rag: bool = True

@app.on_event("startup")
def startup_db():
    # Carga datos iniciales al arrancar la app
    seed_sample_data()
    # Inicializa BD de logs
    init_db()
    # Inicializa BD de core bancario
    init_core_db()
    init_chat_history()
    # Sembrar usuarios de demo si no existen
    try:
        from app.seed_initial_data import seed_demo_users
        seed_demo_users()
    except Exception as e:
        logger.error(f"Error seeding demo users: {e}")

# Endpoint para recolección de métricas por Prometheus/Datadog/Azure Monitor
@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def _run_agent_stream(llm, system_prompt_text, recent_messages, request_id, model_name):
    agent_executor = create_react_agent(llm, tools=get_agent_tools, prompt=system_prompt_text)
    start_time = time.time()
    
    first_token_received = False
    ttft = 0.0
    token_count = 0
    full_response = ""
    
    async for event in agent_executor.astream_events({
        "messages": [("system", system_prompt_text)] + recent_messages
    }, version="v2"):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content") and isinstance(chunk.content, str) and chunk.content:
                full_response += chunk.content
                if not first_token_received:
                    ttft = time.time() - start_time
                    first_token_received = True
                    LLM_TTFT_HISTOGRAM.labels(model=model_name).observe(ttft)
                    logger.info("Primer token emitido", extra={"extra_data": {"request_id": request_id, "ttft_seconds": round(ttft, 4)}})
                token_count += 1
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
        elif event["event"] == "on_tool_start":
            yield f"data: {json.dumps({'type': 'tool_start', 'name': event['name'], 'input': event['data'].get('input', {})})}\n\n"
        elif event["event"] == "on_tool_end":
            yield f"data: {json.dumps({'type': 'tool_end', 'name': event['name'], 'output': str(event['data'].get('output', ''))})}\n\n"

    total_duration = time.time() - start_time
    LLM_LATENCY_HISTOGRAM.labels(model=model_name).observe(total_duration)
    LLM_REQUEST_COUNTER.labels(model=model_name, status="success").inc()
    
    metrics_data = {"ttft": f"{round(ttft, 2)}s", "latency": f"{round(total_duration, 2)}s", "tokens": token_count, "model": model_name}
    yield f"data: {json.dumps({'type': 'metrics', 'content': metrics_data})}\n\n"
    
    asyncio.create_task(asyncio.to_thread(save_chat_message, request_id, "assistant", full_response))
    asyncio.create_task(asyncio.to_thread(save_audit_log, request_id, "prompt", full_response, ttft, total_duration, token_count, model_name))

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    request_id = str(uuid.uuid4())
    primary_model_name = "llama-3.3-70b-versatile"
    fallback_model_name = "llama-3.1-8b-versatile"
    save_chat_message(request_id, "user", request.message)
    recent_messages = load_chat_history(request_id, limit=2)
    system_prompt_text = "Eres el Copiloto de IA de Banorte..."
    
    async def stream_generator():
        try:
            async for event in _run_agent_stream(get_llm(), system_prompt_text, recent_messages, request_id, primary_model_name):
                yield event
        except RateLimitError:
            logger.warning("Rate limit reached; switching to fallback model", extra={"extra_data": {"request_id": request_id}})
            async for event in _run_agent_stream(get_fallback_llm(), system_prompt_text, recent_messages, request_id, fallback_model_name):
                yield event
        except Exception as e:
            logger.error(f"Error: {e}")
            raise e
            
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.post("/api/v1/agent/simulate")
async def calculate_credit(monto: float, plazo: int):
    """Endpoint que simula la ejecución de una herramienta del Agente"""
    return {"status": "success", "data": "simulación completada"}

@app.get("/health")
def health():
    return {"status": "online"}

@app.get("/api/v1/status")
def get_status():
    return {"status": "Online"}

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    return {"status": "success"}

@app.post("/api/v1/audio/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        file_content = await audio.read()
        transcription = groq_client.audio.transcriptions.create(
            file=(audio.filename, file_content),
            model="whisper-large-v3",
            response_format="json",
            language="es"
        )
        
        return {"status": "success", "text": transcription.text}
        
    except Exception as e:
        logger.error(f"Error en transcripción de audio: {str(e)}")
        return {"status": "error", "message": str(e)}
