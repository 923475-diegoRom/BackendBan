from prometheus_client import Counter, Histogram

# Contador total de peticiones por estado y modelo
LLM_REQUEST_COUNTER = Counter(
    "genai_llm_requests_total",
    "Total de peticiones procesadas por el LLM",
    ["model", "status"]
)

# Histograma para la latencia total del LLM
LLM_LATENCY_HISTOGRAM = Histogram(
    "genai_llm_latency_seconds",
    "Tiempo de respuesta total del modelo en segundos",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Histograma para el tiempo hasta el primer token (TTFT)
LLM_TTFT_HISTOGRAM = Histogram(
    "genai_llm_ttft_seconds",
    "Time To First Token (Latencia percibida por el usuario)",
    ["model"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0]
)
