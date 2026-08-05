import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient

load_dotenv()

# Model Context Protocol / LLM: Gemma 2 9B vía Groq
def get_llm():
    return ChatGroq(
        model_name="gemma2-9b-it",
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.2,
        streaming=True
    )

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
