# Banorte GenAI Copilot Backend 🚀

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
