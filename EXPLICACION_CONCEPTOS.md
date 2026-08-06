# 🧠 GUÍA DE CONCEPTOS Y ARQUITECTURA: BACKEND BANORTE GENAI

Este documento es una guía personal explicativa para entender **qué conceptos teóricos** hay detrás del proyecto, **por qué se usaron** y **en qué archivos y líneas exactas de código están implementados**.

---

## 1. Agente de IA vs LLM Tradicional

### 💡 Concepto Teórico
* **LLM tradicional:** Un modelo de lenguaje (como Llama 3 o GPT-4) es solo un "completador de texto". Si le pides *"Transfiérele $500 a Juan"*, el LLM responderá algo como *"Claro, transferí $500 a Juan"* pero **en realidad no hizo nada**, solo generó texto plausible.
* **Agente de IA (ReAct Agent):** Es un LLM equipado con **herramientas (tools)** y un **bucle de razonamiento (Reason + Act)**. Cuando recibe la petición, el LLM decide invocar una función real en código Python, espera el resultado de la base de datos y luego le informa al usuario con datos reales.

### 🔍 ¿Dónde está en nuestro código?
* En [main.py](file:///d:/dr871/Projects/BackendBan/app/main.py#L81):
  ```python
  agent_executor = create_react_agent(llm, tools=tools, prompt=system_prompt_text)
  ```
  Usamos `create_react_agent` de LangGraph para construir este ciclo autogestionado entre la LLM (`ChatGroq`) y nuestras herramientas bancarias.

---

## 2. Herramientas (Tools) y Llamada a Funciones (Tool Calling)

### 💡 Concepto Teórico
Las **Tools** son funciones Python comunes a las que les agregamos un decorador `@tool` con una descripción detallada en texto. El LLM lee estas descripciones y, según la pregunta del usuario, responde con una estructura JSON indicando qué función quiere ejecutar y con qué parámetros.

### 🔍 ¿Dónde está en nuestro código?
* En [agent_tools.py](file:///d:/dr871/Projects/BackendBan/app/agent_tools.py):
  * `obtener_saldo`: Consulta la base de datos de Supabase para ver el saldo real del usuario.
  * `herramienta_transferir_dinero`: Realiza la transacción SQL decrementando la cuenta origen e incrementando la destino.
  * `simular_credito`: Calcula tablas de amortización de préstamos.
  * `herramienta_buscar_info_institucional`: Busca información en la base de datos vectorial Qdrant.

---

## 3. Arquitectura de Grafo y Flujo (LangGraph)

### 💡 Concepto Teórico
En LangGraph, el comportamiento del agente se modela como un **Grafo Dirigido**:
1. **State (Estado):** La lista de mensajes acumulados en la conversación (`[HumanMessage, AIMessage, ToolMessage]`).
2. **Nodes (Nodos):** 
   * Nodo 1: El Modelo LLM (`agent`).
   * Nodo 2: El Ejecutor de Herramientas (`tools`).
3. **Edges (Aristas):** Conexiones condicionales. Si el LLM pide usar una herramienta ➔ va al nodo `tools`. Si el LLM devuelve una respuesta final ➔ va a `END`.

### 🔍 ¿Dónde está en nuestro código?
* Al usar `create_react_agent`, LangGraph construye internamente este flujo:
  ```
  [START] ──> (Nodo: LLM) ───¿Pidio Tool?───> (Nodo: ToolNode)
                   │                                  │
                   └─────── No (Respuesta Final) <────┘
                                   │
                                 [END]
  ```

---

## 4. RAG (Retrieval-Augmented Generation) y Vector Stores

### 💡 Concepto Teórico
El modelo no conoce información interna privada del banco (tarifas, tarjetas específicas, PDFs institucionales). Para resolver esto usamos **RAG**:
1. **Ingestión (Embeddings):** Convertimos PDFs a vectores numéricos (embeddings) con `FastEmbed` y los guardamos en la base de datos **Qdrant**.
2. **Retrieval (Búsqueda):** Cuando el usuario pregunta sobre normas o productos, buscamos los fragmentos de texto matemáticamente más parecidos en Qdrant.
3. **Augmentation:** Le entregamos esos fragmentos al LLM como contexto antes de que responda.

### 🔍 ¿Dónde está en nuestro código?
* En [rag.py](file:///d:/dr871/Projects/BackendBan/app/rag.py):
  * `ingest_pdf()`: Lee un archivo PDF subido por el usuario, lo divide en chunks y lo guarda en Qdrant.
  * `search_qdrant()` / `herramienta_buscar_info_institucional`: Realiza la búsqueda por similitud vectorial.

---

## 5. Memoria Conversacional y Persistencia (`session_id` / `thread_id`)

### 💡 Concepto Teórico
Los modelos de IA no tienen memoria. Cada petición HTTP a un servidor es aislada. Para que la IA "recuerde" quién eres y qué hablaron hace 2 minutos, debemos recargar el historial completo de mensajes asociándolo a un identificador único de sesión (`session_id`).

### 🔍 ¿Dónde está en nuestro código?
* En [database.py](file:///d:/dr871/Projects/BackendBan/app/database.py#L68) y [supabase_audit.py](file:///d:/dr871/Projects/BackendBan/app/supabase_audit.py):
  * Tabla SQLite `chat_messages` guarda cada turno (`user`, `assistant`, `system`).
  * `load_chat_history(session_id)` recupera los mensajes pasados antes de enviar la nueva petición a LangGraph.
  * `save_chat_message(...)` guarda los nuevos mensajes generados.

---

## 6. Autenticación y Seguridad (JWT & Seguridad Financiera)

### 💡 Concepto Teórico
Un agente bancario no puede permitir que un usuario consulte o transfiera dinero de otra cuenta. Necesitamos vincular la sesión del agente al token de autenticación del usuario (`JWT`).

### 🔍 ¿Dónde está en nuestro código?
* En [auth.py](file:///d:/dr871/Projects/BackendBan/app/auth.py) y [agent_tools.py](file:///d:/dr871/Projects/BackendBan/app/agent_tools.py#L112):
  * `get_agent_tools_for_user(user_id)`: Genera un conjunto de herramientas **inyectando el `user_id` autenticado del token**. De esta forma, el LLM nunca recibe ni puede alterar el ID del usuario, garantizando que solo opere sobre la cuenta propia.

---

## 7. Streaming y Servidor Web de Producción (FastAPI + SSE)

### 💡 Concepto Teórico
Esperar 5 u 8 segundos a que el LLM genere la respuesta completa da una mala experiencia de usuario. Usamos **Server-Sent Events (SSE)** para enviar cada palabra (token) al navegador a medida que el LLM la genera.

### 🔍 ¿Dónde está en nuestro código?
* En [main.py](file:///d:/dr871/Projects/BackendBan/app/main.py#L89) y en el endpoint `/api/v1/chat/stream`:
  ```python
  async for event in agent_executor.astream_events(...):
      if event["event"] == "on_chat_model_stream":
          # Se envía cada chunk de texto de inmediato al frontend
  ```

---

## 8. Observabilidad, Métricas y Registro de Auditoría

### 💡 Concepto Teórico
En aplicaciones enterprise y bancarias, es obligatorio saber:
* Latencia total y tiempo al primer token (TTFT - Time To First Token).
* Cuántos tokens se consumieron (costos).
* Registro exacto de qué herramientas ejecutó la IA (Auditoría SQL).

### 🔍 ¿Dónde está en nuestro código?
* En [metrics.py](file:///d:/dr871/Projects/BackendBan/app/metrics.py): Métricas de Prometheus (`LLM_LATENCY_HISTOGRAM`, `LLM_TTFT_HISTOGRAM`).
* En [supabase_audit.py](file:///d:/dr871/Projects/BackendBan/app/supabase_audit.py): `save_audit_log()` registra en la base de datos cada consulta, tokens usados, latencia y modelo ejecutado.

---

## 🗺️ Visión de Conjunto: El Viaje de una Petición

```
   [Usuario en React Frontend]
                │
                │ 1. Petición POST con JWT Token + Mensaje ("Transfiere $100")
                ▼
      [FastAPI: main.py]
                │
                │ 2. Extrae user_id del Token JWT (auth.py)
                │ 3. Recupera historial previo de la sesión (database.py)
                │ 4. Instancia las Tools seguras para ese user_id (agent_tools.py)
                ▼
      [LangGraph: ReAct Agent]
                │
                │ 5. Envía prompt a ChatGroq (Llama 3.3)
                │ 6. LLM responde: "Ejecutar herramienta_transferir_dinero"
                │ 7. LangGraph ejecuta la Tool ➔ Modifica BD Supabase (core_banking.py)
                │ 8. LangGraph regresa al LLM con el resultado exitoso
                ▼
      [Streaming SSE Response]
                │
                │ 9. Emite token por token la confirmación al Frontend
                │ 10. Guarda la interacción en auditoría y métricas Prometheus
                ▼
   [Pantalla del Usuario Actualizada]
```
