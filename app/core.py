import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient

load_dotenv()

# Model Context Protocol / LLM:llama-3.3-70b-versatile  9B vía Groq
def get_llm_by_model(model_name: str):
    """Retorna una instancia de ChatGroq para cualquier modelo especificado."""
    return ChatGroq(
        model_name=model_name,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        streaming=True
    )

def get_llm():
    return get_llm_by_model("qwen/qwen3.6-27b")

def get_fallback_llm():
    return get_llm_by_model("llama-3.1-8b-instant")

# Embeddings de pesos abiertos ultraligeros
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

# Cliente Qdrant Vector Cloud
def get_vector_client():
    return QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
