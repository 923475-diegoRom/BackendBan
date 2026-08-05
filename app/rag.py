from qdrant_client.models import Distance, VectorParams, PointStruct
from app.core import get_vector_client, get_embeddings
import uuid

COLLECTION_NAME = "banorte_productos"

def initialize_collection():
    client = get_vector_client()
    collections = [c.name for c in client.get_collections().collections]
    
    if COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )

def seed_sample_data():
    """Carga inicial de información de productos Banorte"""
    initialize_collection()
    client = get_vector_client()
    embeddings = get_embeddings()
    
    documents = [
        {"text": "Beneficios Tarjeta de Crédito Banorte POR Ti: Bonificación en efectivo de hasta el 2% de tus compras (1% en todas tus compras del mes, y 1% en compras preferidas como Gasolina de Lunes a viernes y Restaurantes Sábado y Domingo). Promoción exclusiva: 6 Meses sin Intereses en tus compras durante los primeros 30 días después de activar tu tarjeta física.", "source": "Folleto_PorTi.pdf"},
        {"text": "Beneficios Tarjeta de Crédito Banorte POR Ti: 12 Meses con Intereses Preferencial pagando cómodamente a 12 Meses con Intereses por compras de $4,000 pesos con una tasa de interés del 23% anual fija. Incluye Banorte Avisa (notificaciones vía SMS sin costo) y protección con Blindaje Banorte hasta 48 horas antes de reporte.", "source": "Folleto_PorTi.pdf"},
        {"text": "Requisitos de Contratación Tarjeta Banorte POR Ti: Ser persona física o con actividad empresarial. Edad de 18 a 69 años 11 meses. Ingreso comprobable bruto mensual mínimo de $7,000.00 pesos mensuales. Buen historial crediticio. Se requiere identificación oficial y comprobante de domicilio e ingresos.", "source": "Folleto_PorTi.pdf"},
        {"text": "Comisiones Tarjeta Banorte POR Ti: Administración de tarjeta del titular $1,150.00 Anual. Administración de tarjeta adicional $470.00 Anual. Reposición de tarjeta por robo o extravío $170.00 por evento. Disposición del crédito en efectivo 6.00% por evento. Penalización por pago tardío $400.00 por evento.", "source": "Folleto_PorTi.pdf"},
        {"text": "Tasas y CAT Tarjeta Banorte POR Ti: CAT PROMEDIO Banorte POR Ti 96.2% sin I.V.A. Tasa de Interés Promedio Ponderada por saldo 64.73% anual sin I.V.A. (variable). Tasa de interés anual ordinaria (variable) T.I.I.E.F. Compuesta por Adelantado a plazo de 28 días + 57 puntos porcentuales.", "source": "Folleto_PorTi.pdf"},
        {"text": "Atención a clientes Banorte: BANORTEL llama sin costo desde cualquier parte de la república al 81-8156-9600. Unidad Especializada de Atención a Usuarios (UNE) al 800-627-2292 o une@banorte.com.", "source": "Folleto_PorTi.pdf"},
        {"text": "El Crédito Hipotecario Banorte requiere un enganche mínimo del 10%, tasa fija anual desde 9.5% y plazo de 10 a 20 años.", "source": "Reglamento_Hipotecario.pdf"}
    ]
    
    points = []
    for doc in documents:
        vector = embeddings.embed_query(doc["text"])
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"text": doc["text"], "source": doc["source"]}
            )
        )
    
    client.upsert(collection_name=COLLECTION_NAME, points=points)

def search_context(query: str, limit: int = 2):
    client = get_vector_client()
    embeddings = get_embeddings()
    query_vector = embeddings.embed_query(query)
    
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit
    ).points
    
    contexts = []
    sources = []
    for res in results:
        contexts.append(res.payload["text"])
        sources.append(res.payload["source"])
        
    return "\\n".join(contexts), list(set(sources))
