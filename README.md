# Banorte GenAI Copilot Backend 🚀

Bienvenido a la documentación exhaustiva del backend del **Copiloto de Inteligencia Artificial Financiera de Banorte**. Este documento está diseñado como una guía técnica detallada paso a paso para estudiar a fondo la arquitectura, algoritmos, flujo de datos y cada uno de los archivos que conforman la carpeta `app/`.

---

## 🏗️ Arquitectura General del Sistema

El backend está construido con una arquitectura moderna de agentes asíncronos y observabilidad distribuida:

- **FastAPI**: Framework web asíncrono en Python de alto rendimiento (`ASGI`).
- **LangChain & LangGraph (`create_react_agent`)**: Orquestación de Agentes de IA ReAct (Reason + Act).
- **Cadena de Fallbacks en Groq (Multi-LLM)**: Cadena secuencial de resiliencia ante límites de cuota (`RateLimitError` 429):
  1. `qwen/qwen3.6-27b` (Modelo Principal)
  2. `llama-3.3-70b-versatile`
  3. `openai/gpt-oss-20b`
  4. `openai/gpt-oss-120b`
  5. `llama-3.1-8b-instant`
  6. `allam-2-7b`
- **Qdrant Cloud**: Base de Datos Vectorial para RAG (Retrieval-Augmented Generation) con búsqueda coseno de 384 dimensiones.
- **HuggingFace Embeddings**: Modelo denso `sentence-transformers/all-MiniLM-L6-v2`.
- **Supabase**: Base de datos relacional PostgreSQL e identidad (Auth, usuarios, tarjetas, contactos y registros de `audit_logs`).
- **Groq Whisper Large v3**: Transcripción de mensajes de voz a texto.
- **Prometheus Client**: Métricas en tiempo real (`LLM_TTFT`, `LLM_LATENCY`, `LLM_REQUESTS`).

---

## 📂 Análisis Detallado Archivo por Archivo (`app/`)

### 1. 🚦 `app/main.py` – Punto de Entrada de la Aplicación
Es el núcleo de la aplicación FastAPI. Administra CORS, inicializa bases de datos al arrancar y expone los endpoints HTTP/SSE:

* **Endpoints Principales**:
  * **`POST /api/v1/chat/stream`**: Recibe `{ message, use_rag, session_id }`, verifica la autenticación mediante token JWT de Supabase, crea las herramientas personalizadas del usuario e inicia el streaming en tiempo real (Server-Sent Events) usando la cadena de fallbacks de LLMs.
  * **`POST /api/v1/documents/upload`**: Recibe un archivo PDF, lo procesa mediante `ingest_pdf()` en `rag.py` y guarda los fragmentos vectorizados en Qdrant.
  * **`POST /api/v1/audio/transcribe`**: Recibe un archivo de audio (`UploadFile`), invoca Whisper Large v3 en Groq y retorna el texto transcrito.
  * **`GET /api/v1/status`**: Devuelve la salud de la API, latencia promedio calculada en vivo y rendimiento de tokens (`tok/s`).
  * **`GET /metrics`**: Expone métricas estándar para recolección con Prometheus / Datadog.

---

### 2. 🤖 `app/agent_tools.py` – Herramientas Determinísticas del Agente
Define las herramientas (Tools) que el Agente ReAct del LLM puede decidir ejecutar dinámicamente. Todas las herramientas están aisladas de forma segura por usuario mediante la fábrica `get_agent_tools_for_user(user_id)`:

* **`herramienta_ver_saldo()`**: Consulta el saldo real del usuario autenticado en la tabla `users` de Supabase.
* **`herramienta_ver_productos()`**: Muestra las tarjetas y créditos contratados en la tabla `productos`.
* **`herramienta_ver_contactos()`**: Retorna la lista de contactos frecuentes formateados en México (`es_MX`).
* **`herramienta_ver_transacciones()`**: Muestra el historial de movimientos de la cuenta.
* **`herramienta_transferir_dinero(cuenta_destino, monto)`**: Valida fondos suficientes, descuenta el saldo del usuario e inserta la transacción.
* **`herramienta_simular_credito(monto, plazo_anios)`**: Calcula la cuota mensual fija usando la fórmula de amortización.
* **`herramienta_buscar_info_institucional(pregunta)`**: Ejecuta la búsqueda vectorial en Qdrant y devuelve un JSON estructurado con la información y las fuentes oficiales (`fuentes_usadas`).

---

### 3. 🧠 `app/rag.py` – RAG y Base de Datos Vectorial Qdrant
Implementa la lógica de Retrieval-Augmented Generation con Qdrant y embeddings densos:

* **`seed_sample_data()`**: Inicializa la colección `banorte_productos` (384 dimensiones, distancia Coseno). Verifica previamente el número de puntos con `client.count()` para evitar duplicar información al reiniciar el servidor.
* **`search_context(query, limit=2)`**: Convierte la consulta del usuario en un vector denso con `all-MiniLM-L6-v2` y realiza una búsqueda HNSW de K-Vecinos más cercanos (k-NN) en Qdrant.
* **`ingest_pdf(file_bytes, filename)`**: Extrae el texto del PDF con `PdfReader`, lo divide en fragmentos con `RecursiveCharacterTextSplitter` (1000 caracteres, 200 overlap), genera embeddings e inserta los vectores en Qdrant.

---

### 4. 🔑 `app/auth.py` – Autenticación y Gestión de Perfiles
Gestiona la autenticación con Supabase Auth e integración de perfiles:

* **`POST /signup`**: Registra un nuevo usuario en Supabase Auth y le asigna un perfil bancario real existente de la tabla `users` para no saturar con usuarios *dummy*.
* **`POST /login`**: Autentica usuarios con email/password y devuelve un JWT access token.
* **`GET /me`**: Devuelve los detalles del usuario logueado (saldo, tarjeta, contactos).
* **`verify_token()`**: Middleware de seguridad `HTTPBearer` que valida los tokens JWT contra Supabase.

---

### 5. 🗄️ `app/supabase_audit.py`, `app/supabase_client.py` y `app/supabase_helper.py` – Persistencia en Supabase
Reemplaza la persistencia local/SQLite por una infraestructura en la nube con Supabase (PostgreSQL):

* **`supabase_client.py`**: Instancia el cliente de Supabase usando `SUPABASE_URL` y la clave de servicio `SUPABASE_SERVICE_ROLE_KEY`.
* **`supabase_helper.py`**: Wrapper genérico que abstrae operaciones CRUD (`select`, `insert`, `update`).
* **`supabase_audit.py`**: Persiste el historial de conversaciones en `chat_messages` y guarda la auditoría de rendimiento en `audit_logs` (registrando `request_id`, `user_message`, `bot_response`, `ttft`, `total_time`, `tokens` y `model_name`).

---

### 6. 🏦 `app/core_banking.py` – Módulo Bancario Core
Contiene la lógica de negocio para operaciones sobre las cuentas:

* `consultar_saldo()`, `consultar_productos()`, `consultar_contactos()`, `consultar_transacciones()` y `hacer_transferencia()`. Todos operan contra las tablas de Supabase garantizando el aislamiento por `user_id`.

---

### 7. 🧮 `app/tools.py` – Calculadora Financiera Determinística
Contiene la función matemática `simular_credito`:
\[
\text{Mensualidad} = \frac{P \times r}{1 - (1 + r)^{-n}}
\]
Donde $P$ es el monto, $r$ es la tasa mensual ($9.5\% / 12$) y $n$ es el número de meses ($plazo \times 12$).

---

### 8. ⚙️ `app/core.py` – Clientes y Factory de LLMs
Configura las conexiones principales:
* **`get_llm_by_model(model_name)`**: Instancia `ChatGroq` de forma dinámica para cualquier modelo.
* **`get_embeddings()`**: Inicializa `HuggingFaceEmbeddings` (`sentence-transformers/all-MiniLM-L6-v2`).
* **`get_vector_client()`**: Retorna la conexión a Qdrant Cloud.

---

### 9. 📊 `app/logger.py` & `app/metrics.py` – Observabilidad
* **`logger.py`**: Proporciona logging estructurado en formato JSON con metadatos contextuales (`request_id`, `ttft_seconds`).
* **`metrics.py`**: Define métricas globales de Prometheus:
  * `LLM_REQUEST_COUNTER`: Contador de peticiones por modelo y estatus.
  * `LLM_LATENCY_HISTOGRAM`: Histograma de latencia total.
  * `LLM_TTFT_HISTOGRAM`: Histograma del tiempo transcurrido hasta el primer token emitido (Time To First Token).

---

## 🔄 Flujo de una Petición de Chat (`/api/v1/chat/stream`)

1. **Recepción**: El usuario envía su mensaje desde la UI junto con su token JWT.
2. **Autenticación**: `auth_header` extrae el `profile_id` del usuario autenticado.
3. **Instanciación de Herramientas**: Se cargan únicamente las herramientas asociadas al `user_id` del usuario.
4. **Agente ReAct**: `create_react_agent` evalúa el mensaje. Si el usuario pregunta por un saldo o políticas, el agente decide ejecutar la herramienta adecuada (`on_tool_start` -> `on_tool_end`).
5. **Generación con Fallback Chain**: Intenta generar la respuesta token por token vía SSE. Si el modelo actual alcanza un error 429 (`RateLimitError`), salta automáticamente al siguiente modelo de la cadena.
6. **Métricas y Auditoría**: Se calcula TTFT, tiempo total y cantidad de tokens; finalmente se guarda el registro de auditoría en la tabla `audit_logs` de Supabase.

---

## 🚀 Cómo Ejecutar el Backend Localmente

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Iniciar servidor FastAPI con Uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
