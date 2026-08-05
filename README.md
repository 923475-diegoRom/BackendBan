# Banorte GenAI Copilot Backend 🚀

Este repositorio contiene el backend de un **Copiloto de Inteligencia Artificial Financiera** con arquitectura moderna, RAG, transcripción de voz y, **nueva funcionalidad de persistencia de historial de chat**.

---

## 🏗️ Arquitectura y Stack Tecnológico

- **FastAPI** – API asíncrona de alto rendimiento.
- **Groq (Llama 3.3 70B)** – Modelo LLM rápido vía streaming.
- **Qdrant** – Base de datos vectorial para RAG.
- **Whisper Large v3 (Groq)** – Speech‑to‑Text.
- **SQLite Cloud** – Almacén de auditoría y ahora de historial de chat.
- **Prometheus** – Métricas y observabilidad.

---

## 📂 Estructura del proyecto y módulos principales

### 1. `app/main.py` – Punto de entrada de la API
- **`POST /api/v1/chat/stream`** – Recibe `message`, `use_rag` y **`session_id`**. Cada `request_id` del backend se usa como `session_id` y se persiste en la tabla `chat_messages`.
- **`POST /api/v1/audio/transcribe`** – Convierte audio a texto usando Whisper.
- **`POST /api/v1/documents/upload`** – Ingesta PDFs en Qdrant.
- **`GET /api/v1/chat/history/{session_id}`** – **Nuevo endpoint** que devuelve el historial completo (en orden cronológico) para una sesión dada.
- **`GET /metrics` & `GET /api/v1/status`** – Salud y métricas.

### 2. `app/database.py`
- **`init_chat_history()`** – Crea la tabla `chat_messages` (`id`, `session_id`, `role`, `content`, `timestamp`).
- **`save_chat_message(session_id, role, content)`** – Inserta cada turno del chat (usuario o asistente).
- **`load_chat_history(session_id, limit=100)`** – Recupera los últimos `limit` mensajes para la sesión.
- Estas funciones se llaman desde `app/main.py`:
  - En el endpoint `/chat/stream` se guarda el mensaje del usuario y la respuesta del asistente usando el mismo `session_id`.
  - En `startup` se ejecuta `init_chat_history()` para asegurar que la tabla exista.

### 3. `app/core.py` – Configuración e integraciones
- Clientes LLM, embeddings y Qdrant.

### 4. `app/rag.py` – Búsqueda aumentada (RAG)
- `search_context(query)` y `ingest_pdf()`.

### 5. `app/tools.py` – Herramientas determinísticas
- `simular_credito`, entre otras.

### 6. `app/logger.py` & `app/metrics.py` – Observabilidad con Prometheus.

---

## 🔄 Flujo de conversación (incluye historial)
1. **Frontend** genera/recupera `sessionId` (almacenado en `localStorage`).
2. Envía `POST /api/v1/chat/stream` con `{ message, use_rag, session_id }`.
3. En el backend:
   - Se crea `request_id` (`UUID4`) y se usa como `session_id` si no se envía (el frontend siempre lo envía).
   - `save_chat_message(session_id, 'user', message)` persiste el mensaje del cliente.
   - Se procesa RAG (si está activo) y se llama al LLM.
   - Cada token se envía por SSE al cliente.
   - Al terminar, `save_chat_message(session_id, 'assistant', full_response)` persiste la respuesta completa.
4. Cuando el usuario recarga la página, el frontend llama `GET /api/v1/chat/history/{session_id}` para cargar el historial y mostrárselo.

---

## 📄 Nuevo endpoint de historial
```http
GET /api/v1/chat/history/{session_id}?limit=100
```
- Devuelve un JSON con una lista de objetos `{ role, content, timestamp }` ordenados cronológicamente.
- Ideal para cargar conversaciones previas al iniciar la UI.

---

## 🛠️ Posibles mejoras (ideas para entrevista)
- **Persistencia robusta**: Migrar de SQLite Cloud a PostgreSQL para mayor escalabilidad.
- **Re‑ranking**: Aplicar un Cross‑Encoder después de la búsqueda en Qdrant.
- **Agentes LangChain/LlamaIndex**: Permitir al LLM decidir cuándo invocar herramientas.
- **Autenticación de sesiones**: Vincular `session_id` a usuarios autenticados.

---

## 🚀 Cómo iniciar el proyecto
```bash
# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno (ejemplo .env)
export GROQ_API_KEY=your_key
export QDRANT_URL=http://localhost:6333
export SQLITE_URL=https://<your-sqlite-cloud>.sqlite3

# Ejecutar
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

*Este README se mantiene actualizado para la versión actual del proyecto y está pensado para ser usado en entrevistas técnicas, mostrando la arquitectura, el flujo de datos y los puntos críticos de observabilidad.*
