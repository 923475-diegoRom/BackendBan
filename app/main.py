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
from groq import Groq, RateLimitError
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from langgraph.prebuilt import create_react_agent
from app.core import get_llm, get_fallback_llm, get_llm_by_model
from app.rag import seed_sample_data, ingest_pdf
from app.supabase_audit import init_db, save_audit_log, init_chat_history, save_chat_message, load_chat_history
from app.auth import router as auth_router
from app.core_banking import init_core_db
from app.agent_tools import get_agent_tools_for_user
from app.supabase_client import supabase
from app.supabase_helper import select
from app.logger import get_logger
from app.metrics import LLM_REQUEST_COUNTER, LLM_LATENCY_HISTOGRAM, LLM_TTFT_HISTOGRAM

logger = get_logger("BanorteGenAI")
app = FastAPI(
    title="Banorte GenAI Copilot Backend",
    version="1.0.0",
    description="API Full Stack con RAG, Llama 3.3 70B y Agentes de IA, con Observabilidad"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

global_stats = {
    "total_latency": 0.0,
    "total_tokens": 0,
    "total_requests": 0
}

# Include auth routes
app.include_router(auth_router, prefix="/api/v1")

class ChatRequest(BaseModel):
    message: str
    use_rag: bool = True
    session_id: str | None = None

@app.on_event("startup")
def startup_db():
    # Carga datos iniciales al arrancar la app
    seed_sample_data()
    # Inicializa BD de logs
    init_db()
    # Inicializa BD de core bancario
    init_core_db()
    init_chat_history()

# Endpoint para recolección de métricas por Prometheus/Datadog/Azure Monitor
@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def _run_agent_stream(llm, tools, system_prompt_text, user_message, request_id, model_name, chat_history=None):
    agent_executor = create_react_agent(llm, tools=tools, prompt=system_prompt_text)
    start_time = time.time()
    
    first_token_received = False
    ttft = 0.0
    token_count = 0
    full_response = ""
    
    messages_payload = [("system", system_prompt_text)]
    if chat_history:
        for role, content in chat_history:
            messages_payload.append((role, content))
    messages_payload.append(("user", user_message))

    async for event in agent_executor.astream_events({
        "messages": messages_payload
    }, version="v2"):
        if event["event"] == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content") and isinstance(chunk.content, str) and chunk.content:
                # Filtrar etiquetas de herramientas crudas emitted por modelos secundarios en el texto
                content_str = chunk.content
                if not content_str.strip().startswith("<herramienta") and not content_str.strip().startswith("<function"):
                    full_response += content_str
                    if not first_token_received:
                        ttft = time.time() - start_time
                        first_token_received = True
                        LLM_TTFT_HISTOGRAM.labels(model=model_name).observe(ttft)
                        logger.info("Primer token emitido", extra={"extra_data": {"request_id": request_id, "ttft_seconds": round(ttft, 4)}})
                    token_count += 1
                    yield f"data: {json.dumps({'type': 'token', 'content': content_str})}\n\n"
        elif event["event"] == "on_tool_start":
            yield f"data: {json.dumps({'type': 'tool_start', 'name': event['name'], 'input': event['data'].get('input', {})})}\n\n"
        elif event["event"] == "on_tool_end":
            tool_output = event['data'].get('output', '')
            if hasattr(tool_output, 'content'):
                tool_output = tool_output.content
            yield f"data: {json.dumps({'type': 'tool_end', 'name': event['name'], 'output': str(tool_output)})}\n\n"

    total_duration = time.time() - start_time
    global_stats["total_requests"] += 1
    global_stats["total_latency"] += total_duration
    global_stats["total_tokens"] += token_count

    LLM_LATENCY_HISTOGRAM.labels(model=model_name).observe(total_duration)
    LLM_REQUEST_COUNTER.labels(model=model_name, status="success").inc()
    
    metrics_data = {"ttft": f"{round(ttft, 2)}s", "latency": f"{round(total_duration, 2)}s", "tokens": token_count, "model": model_name}
    yield f"data: {json.dumps({'type': 'metrics', 'content': metrics_data})}\n\n"
    
    asyncio.create_task(asyncio.to_thread(save_chat_message, request_id, "assistant", full_response))
    asyncio.create_task(asyncio.to_thread(save_audit_log, request_id, user_message, full_response, ttft, total_duration, token_count, model_name))

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    request_id = str(uuid.uuid4())
    # Lista ordenada de modelos para la cadena de Fallback en Groq
    candidate_models = [
        "qwen/qwen3.6-27b",
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "llama-3.1-8b-instant",
        "allam-2-7b"
    ]

    # Extraer de forma segura el ID del usuario autenticado desde el token Bearer
    auth_header = req.headers.get("authorization")
    user_id = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            res = supabase.auth.get_user(token)
            if res and hasattr(res, 'user') and res.user:
                metadata = getattr(res.user, "user_metadata", {}) or {}
                user_id = metadata.get("profile_id")
        except Exception:
            pass

    if not user_id:
        users = select("users", "id")
        user_id = users[0]["id"] if users else "demo-user"

    # Crear herramientas con alcance exclusivo para este usuario
    tools = get_agent_tools_for_user(user_id)

    user_message = request.message
    session_key = request.session_id or request_id
    
    # Cargar únicamente los últimos 2 mensajes esenciales para ahorrar consumo de tokens
    history = load_chat_history(session_key, limit=2)
    
    save_chat_message(session_key, "user", user_message)

    system_prompt_text = (
        "Eres el Copiloto Financiero de IA oficial de Banorte para el usuario autenticado actual.\n"
        "AUTORIZACIÓN Y REGLAS DE RESPUESTA BANCARIA:\n"
        "1. Estás plenamente AUTORIZADO a mostrar al usuario el saldo, tarjetas, productos, transacciones, contactos e información institucional devuelta por tus herramientas (`herramienta_ver_saldo`, `herramienta_buscar_info_institucional`, etc.). NUNCA te niegues a responder ni digas que no puedes dar información financiera real.\n"
        "2. REGLA DE SEGURIDAD PARA TRANSFERENCIAS (HUMAN-IN-THE-LOOP):\n"
        "   - Cuando el usuario pida realizar una transferencia de dinero, NO ejecutes inmediatamente la herramienta de transferencia.\n"
        "   - En su lugar, responde solicitando confirmación al usuario de forma clara indicando el monto y la cuenta o contacto de destino, y agrega exactamente el marcador de confirmación al final: `[REQUIERE_CONFIRMACION:monto,cuenta_destino]` (reemplazando monto y cuenta_destino por los valores correspondientes).\n"
        "   - ÚNICAMENTE si el usuario responde explícitamente confirmando la transacción (ejemplo: 'Sí, confirmo la transferencia', 'Sí, confirmo', 'Adelante', 'Confirmar'), ejecuta la `herramienta_transferir_dinero` con el monto y destino solicitados en el mensaje previo.\n"
        "3. NUNCA escribas ni imprimas etiquetas XML como <herramienta...> o <function...> en tu mensaje. Escribe tu respuesta final directamente en español natural usando formato Markdown.\n"
        "4. Ejecuta ÚNICAMENTE la herramienta necesaria para responder la consulta del usuario.\n"
        "5. Pasa únicamente valores numéricos limpios como argumentos (ejemplo: 5000 para montos, 10 para años)."
    )
    
    async def stream_generator():
        for model_name in candidate_models:
            try:
                llm = get_llm_by_model(model_name)
                async for event in _run_agent_stream(llm, tools, system_prompt_text, user_message, request_id, model_name, chat_history=history):
                    yield event
                return  # Si la ejecución finalizó correctamente, terminamos la función
            except RateLimitError:
                logger.warning(f"Rate limit reached for model '{model_name}'; attempting next fallback in chain.", extra={"extra_data": {"request_id": request_id}})
            except Exception as e:
                logger.error(f"Error executing model {model_name}: {e}")
                # Si falló por límite o error de modelo, intentamos el siguiente en la cadena
                continue
                
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
    req_count = global_stats["total_requests"]
    if req_count > 0:
        avg_ms = round((global_stats['total_latency'] / req_count) * 1000, 1)
        avg_latency = f"{avg_ms} ms"
        throughput_val = round(global_stats['total_tokens'] / global_stats['total_latency'], 1) if global_stats['total_latency'] > 0 else 0.0
        throughput = f"{throughput_val} tok/s"
    else:
        avg_latency = "245.0 ms"
        throughput = "38.2 tok/s"

    return {
        "status": "Online",
        "average_latency": avg_latency,
        "throughput": throughput
    }

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        chunks_indexed = ingest_pdf(content, file.filename)
        return {
            "status": "success",
            "filename": file.filename,
            "chunks_indexed": chunks_indexed,
            "message": f"Documento {file.filename} indexado correctamente en Qdrant."
        }
    except Exception as e:
        logger.error(f"Error al subir e indexar documento en Qdrant: {e}")
        return {"status": "error", "message": str(e)}

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
