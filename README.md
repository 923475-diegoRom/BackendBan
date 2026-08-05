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

El backend ahora guarda automáticamente cada turno del chat, permitiendo cargar historiales y ofrecer una mejor experiencia de conversación continua.


Este repositorio contiene el backend de un **Copiloto de Inteligencia Artificial Financiera**, diseñado con arquitectura moderna, capacidades de Recuperación de Información (RAG), transcripción de voz y alta observabilidad. 

Es una API RESTful robusta construida con **FastAPI** y pensada para integrarse fluidamente con aplicaciones web modernas.

---

## 🏗️ Arquitectura y Stack Tecnológico

El proyecto está construido sobre las siguientes tecnologías clave:

- **Framework Web**: [FastAPI](https://fastapi.tiangolo.com/) - Elegido por su altísimo rendimiento (basado en Starlette y Pydantic), soporte asíncrono nativo (`async/await`) y autogeneración de documentación (Swagger UI).
- **Motor de Inferencia (LLM)**: **Llama 3.3 70B** a través de la API de **Groq**. Groq utiliza unidades de procesamiento de lenguaje (LPUs) que ofrecen una velocidad de generación de tokens extremadamente rápida, ideal para respuestas en tiempo real (streaming).
- **Base de Datos Vectorial**: **Qdrant** - Utilizado para almacenar los vectores de los documentos y realizar búsquedas de similitud (búsqueda semántica) ultrarrápidas para el RAG.
- **Voz a Texto (Speech-to-Text)**: **Whisper Large v3** (vía Groq) - Para convertir el dictado por voz del usuario en texto de forma instantánea.
- **Observabilidad**: **Prometheus** (para métricas de rendimiento) y logging estructurado personalizado.

---

## 📂 Estructura del Proyecto y Módulos Principales

El código está modularizado para mantener la separación de responsabilidades (Clean Code). A continuación, se detalla qué hace cada archivo:

### 1. `app/main.py` (El Corazón de la API)
Es el punto de entrada de la aplicación. Define la configuración de CORS, el middleware, y todos los endpoints expuestos hacia el frontend:
- **`POST /api/v1/chat/stream`**: El endpoint más importante. Recibe la consulta del usuario, busca contexto en la base de datos vectorial (si RAG está activado), inyecta este contexto en un *System Prompt*, y hace una petición asíncrona al LLM. La respuesta se devuelve al cliente en pequeños pedazos (chunks) usando **Server-Sent Events (SSE)**, lo que crea el efecto visual de "escritura en tiempo real".
- **`POST /api/v1/audio/transcribe`**: Recibe un archivo de audio (ej. grabado desde el micrófono en la web), lo sube temporalmente en memoria y utiliza el modelo Whisper para devolver el texto transcrito.
- **`POST /api/v1/documents/upload`**: Endpoint para ingerir nuevos conocimientos. Recibe un PDF, extrae su texto, lo divide en fragmentos (chunks) y los guarda en Qdrant.
- **`GET /metrics` & `/api/v1/status`**: Endpoints para monitorear la salud, latencia y rendimiento del servidor.

### 2. `app/core.py` (Configuración e Integraciones)
Maneja las conexiones con servicios externos utilizando el patrón de diseño *Factory*.
- **`get_llm()`**: Inicializa el cliente `ChatGroq` apuntando al modelo Llama 3.3.
- **`get_embeddings()`**: Configura el modelo de embeddings `sentence-transformers/all-MiniLM-L6-v2` desde HuggingFace. Este modelo ligero convierte texto a vectores matemáticos.
- **`get_vector_client()`**: Inicializa la conexión con la base de datos Qdrant.

### 3. `app/rag.py` (Retrieval-Augmented Generation)
Toda la inteligencia de búsqueda documental vive aquí.
- **`search_context(query)`**: Convierte la pregunta del usuario en un vector matemático y busca en Qdrant los fragmentos de texto más similares (usando similitud del coseno). Esto le da "memoria" al LLM sobre documentos internos (como reglas de tarjetas de crédito).
- **`ingest_pdf()`**: Lee un PDF, extrae todo el texto, lo divide en bloques de 1000 caracteres (con 200 de superposición para no perder contexto) usando `RecursiveCharacterTextSplitter`, genera los embeddings y los inserta en Qdrant.

### 4. `app/tools.py` (Agentes y Herramientas)
Contiene las funciones "deterministas" que la IA puede utilizar.
- **`simular_credito(monto, plazo)`**: Una calculadora financiera pura en Python. Mientras que el LLM genera texto, este tipo de herramientas se usan para hacer cálculos matemáticos exactos (como amortizaciones hipotecarias) que los modelos de lenguaje no saben hacer de forma confiable.

### 5. `app/logger.py` y `app/metrics.py` (Observabilidad)
- Implementan contadores y cronómetros (Histogramas) de **Prometheus** para medir cosas críticas como el **TTFT (Time To First Token)**, latencia total y tasa de errores. Esto es crucial en arquitecturas de IA empresariales para saber si el modelo de lenguaje está degradando la experiencia del usuario.

---

## 🔄 Flujos Clave para Explicar en una Entrevista

Si te preguntan **"¿Cómo funciona cuando un usuario manda un mensaje?"**, puedes responder con este flujo:

1. **Recepción**: El Frontend manda un `POST` a `/chat/stream` con la pregunta (ej. "¿Cuál es la tasa de la tarjeta?").
2. **Embeddings & Vector Search (RAG)**: El backend pasa esa pregunta por el modelo *MiniLM* para obtener un vector. Luego, busca en *Qdrant* los textos más matemáticamente similares a ese vector.
3. **Prompt Engineering**: Se construye un "Prompt" maestro que incluye las instrucciones de comportamiento (System Prompt) + El contexto recuperado de Qdrant + La pregunta original.
4. **Inferencia & Streaming**: Se envía este gran prompt a *Groq (Llama 3.3)*. En lugar de esperar a que termine toda la respuesta, FastAPI utiliza `StreamingResponse` para iterar sobre el generador asíncrono y enviar cada palabra al frontend en el instante en que se genera.

---

## 🛠️ Posibles Mejoras (Ideas para destacar en tu entrevista)
- **Persistencia de Historial**: Implementar SQLite o PostgreSQL para guardar los historiales de los chats y mantener contexto de conversaciones largas.
- **Re-ranking**: Aplicar un modelo de "Cross-Encoder" después de Qdrant para ordenar los resultados encontrados del RAG y darle al LLM solo la información más relevante.
- **Agentes Reales**: Integrar LangChain Tools o LlamaIndex Agents para que el LLM decida autónomamente cuándo llamar a `simular_credito` basado en la intención del usuario.
