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

from app.core import get_llm
from app.rag import search_context, seed_sample_data, ingest_pdf
from app.tools import simular_credito
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
    allow_origins=["*"],
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

# Endpoint para recolección de métricas por Prometheus/Datadog/Azure Monitor
@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    request_id = str(uuid.uuid4())
    model_name = "llama-3.3-70b-versatile"

    logger.info(
        f"Iniciando solicitud de IA stream", 
        extra={"extra_data": {"request_id": request_id, "prompt_length": len(request.message)}}
    )

    llm = get_llm()
    sources = []
    context = ""
    
    if request.use_rag:
        context, sources = search_context(request.message)
    
    system_prompt = f"""
    Eres el Copiloto de Inteligencia Artificial de Banorte.
    Responde al usuario de manera profesional, clara y concisa.
    
    Contexto de apoyo disponible:
    {context}
    
    Pregunta del usuario: {request.message}
    """
    
    start_time = time.time()
    
    async def generate_with_trace():
        first_token_received = False
        ttft = 0.0
        token_count = 0
        
        try:
            # Enviar las fuentes primero si existen
            if sources:
                yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"
            
            async for chunk in llm.astream(system_prompt):
                if chunk.content:
                    # Medir Time To First Token (TTFT) en la primera emisión de token
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
