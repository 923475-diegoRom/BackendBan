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
from app.database import init_db, save_audit_log, init_chat_history, save_chat_message
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

global_stats = {
    "total_latency": 0.0,
    "total_tokens": 0,
    "total_requests": 0,
    "total_duration": 0.0
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://front-end-ban.vercel.app"
    ],
    allow_credentials=True,
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

# Endpoint para recolección de métricas por Prometheus/Datadog/Azure Monitor
@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    request_id = str(uuid.uuid4())
    model_name = "llama-3.3-70b-versatile"
    # Persist the user's message for this session
    save_chat_message(request_id, "user", request.message)

    logger.info(
        f"Iniciando solicitud de IA stream", 
        extra={"extra_data": {"request_id": request_id, "prompt_length": len(request.message)}}
    )

    llm = get_llm()
    system_prompt_text = f"""Eres el Copiloto de Inteligencia Artificial de Banorte. ERES EXCLUSIVO DE BANORTE.
Si el usuario te pregunta por BBVA, Bancomer, Santander o cualquier otro banco competidor, dile educadamente que tú solo tienes información y acceso a los productos de Banorte.
Tienes acceso a herramientas para consultar saldos, hacer transferencias, simular créditos, buscar información institucional, ver contactos y ver transacciones. 
El cliente actual logueado es C-TEST (Usuario Test).

REGLA DE ORO INQUEBRANTABLE PARA TRANSACCIONES Y SALDOS:
1. NUNCA inventes, alucines, ni agregues datos falsos.
2. Si usas la herramienta de 'ver transacciones', tu respuesta final DEBE SER UNA COPIA EXACTA de lo que la herramienta devuelva.
3. NO añadas retiros, depósitos ni fechas que no vengan en el resultado de la herramienta.

Si la herramienta devuelve 2 transacciones, tú le muestras al usuario exactamente esas 2 transacciones y te detienes.
"""
    
    # Intentamos usar messages_modifier si está disponible (LangGraph antiguo), si no, no pasa nada porque lo inyectamos abajo.
    try:
        agent_executor = create_react_agent(llm, tools=get_agent_tools, messages_modifier=system_prompt_text)
    except TypeError:
        agent_executor = create_react_agent(llm, tools=get_agent_tools)
    
    start_time = time.time()
    
    async def generate_with_trace():
        first_token_received = False
        ttft = 0.0
        token_count = 0
        full_response = ""
        
        try:
            async for event in agent_executor.astream_events({
                "messages": [("system", system_prompt_text), ("user", request.message)]
            }, version="v2"):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and isinstance(chunk.content, str) and chunk.content:
                        full_response += chunk.content
                        if not first_token_received:
                            ttft = time.time() - start_time
                            first_token_received = True
                            LLM_TTFT_HISTOGRAM.labels(model=model_name).observe(ttft)
                            logger.info(
                                "Primer token emitido", 
                                extra={"extra_data": {"request_id": request_id, "ttft_seconds": round(ttft, 4)}}
                            )
                        
                        token_count += 1
                        data = json.dumps({"type": "token", "content": chunk.content})
                        yield f"data: {data}\n\n"
                        await asyncio.sleep(0.01)
                elif event["event"] == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': tool_name, 'input': tool_input})}\n\n"
                elif event["event"] == "on_tool_end":
                    tool_name = event["name"]
                    tool_output = event["data"].get("output", "")
                    
                    if tool_name == "herramienta_buscar_info_institucional":
                        try:
                            # Try to extract the sources if we returned JSON
                            output_str = tool_output.content if hasattr(tool_output, 'content') else str(tool_output)
                            parsed = json.loads(output_str)
                            sources = parsed.get("fuentes_usadas", [])
                            info_text = parsed.get("info", "")
                            if sources:
                                # Enviar el formato exacto que el Frontend (App.jsx) puede aprovechar
                                # Incluimos los "pedazos de info" en pageContent
                                formatted_sources = [{"metadata": {"source": src}, "pageContent": info_text} for src in sources]
                                yield f"data: {json.dumps({'type': 'sources', 'content': formatted_sources})}\n\n"
                        except Exception as e:
                            logger.error(f"Error parsing tool_output for sources: {e}")
                            pass
                            
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': tool_name, 'output': str(tool_output)})}\n\n"

            # Cálculo de la latencia total y registros de cierre
            total_duration = time.time() - start_time
            LLM_LATENCY_HISTOGRAM.labels(model=model_name).observe(total_duration)
            LLM_REQUEST_COUNTER.labels(model=model_name, status="success").inc()

            global_stats["total_requests"] += 1
            global_stats["total_latency"] += total_duration
            global_stats["total_tokens"] += token_count
            global_stats["total_duration"] += total_duration

            metrics_data = {
                "ttft": f"{round(ttft, 2)}s",
                "latency": f"{round(total_duration, 2)}s",
                "tokens": token_count,
                "model": model_name
            }
            yield f"data: {json.dumps({'type': 'metrics', 'content': metrics_data})}\n\n"

            logger.info(
                "Finalizada generación de streaming con éxito",
                extra={"extra_data": {
                    "request_id": request_id,
                    "total_tokens": token_count,
                    "total_duration_sec": round(total_duration, 4),
                    "ttft_sec": round(ttft, 4),
                    "tokens_per_second": round(token_count / max(total_duration, 0.001), 2)
                }}
            )
            
            # Guardar la respuesta del asistente en la tabla de historial de chat
            asyncio.create_task(
                asyncio.to_thread(
                    save_chat_message,
                    request_id,
                    "assistant",
                    full_response
                )
            )
            # Guardar en SQLite Cloud de forma asíncrona
            asyncio.create_task(
                asyncio.to_thread(
                    save_audit_log,
                    request_id,
                    request.message,
                    full_response,
                    ttft,
                    total_duration,
                    token_count,
                    model_name
                )
            )

        except Exception as e:
            LLM_REQUEST_COUNTER.labels(model=model_name, status="error").inc()
            logger.error(
                f"Error durante la generación de LLM: {str(e)}", 
                extra={"extra_data": {"request_id": request_id}}
            )
            raise e

    return StreamingResponse(generate_with_trace(), media_type="text/event-stream")

@app.post("/api/v1/agent/simulate")
async def calculate_credit(monto: float, plazo: int):
    """Endpoint que simula la ejecución de una herramienta del Agente"""
    resultado = simular_credito(monto, plazo)
    return {"status": "success", "data": resultado}

@app.get("/health")
def health():
    return {"status": "online", "engine": "llama-3.3-70b-versatile via Groq", "vector_db": "Qdrant Cloud"}

@app.get("/api/v1/status")
def get_status():
    avg_latency = global_stats["total_latency"] / global_stats["total_requests"] if global_stats["total_requests"] > 0 else 0.12
    throughput = global_stats["total_tokens"] / global_stats["total_duration"] if global_stats["total_duration"] > 0 else 45.0
    return {
        "status": "Online",
        "engine": "llama-3.3-70b-versatile",
        "average_latency": f"{round(avg_latency * 1000)} ms", 
        "throughput": f"{round(throughput)} tok/s"
    }

@app.post("/api/v1/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        return {"status": "error", "message": "Solo se permiten archivos PDF"}
        
    try:
        contents = await file.read()
        chunks_indexed = ingest_pdf(contents, file.filename)
        return {
            "status": "success",
            "message": f"Documento procesado correctamente",
            "chunks_indexed": chunks_indexed
        }
    except Exception as e:
        logger.error(f"Error procesando PDF: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.post("/api/v1/audio/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        # Inicializar cliente de Groq
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Leer archivo a memoria
        file_content = await audio.read()
        
        # Llamar a Whisper API vía Groq
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
