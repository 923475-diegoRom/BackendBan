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
        {"text": "La Tarjeta de Crédito Banorte Por Ti ofrece 1.5% de cashback en compras de supermercado y no cobra anualidad el primer año.", "source": "Folleto_PorTi.pdf"},
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
    
    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit
    )
    
    contexts = []
    sources = []
    for res in results:
        contexts.append(res.payload["text"])
        sources.append(res.payload["source"])
        
    return "\\n".join(contexts), list(set(sources))
