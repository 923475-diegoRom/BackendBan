"""Supabase based persistence for audit logs and chat history.

Provides thin wrappers around the Supabase client for the operations that were
previously performed with SQLite Cloud.
"""

from app.supabase_helper import insert, select

# Table names – adjust if your Supabase schema uses different names.
import logging

logger = logging.getLogger("BanorteGenAI")

# Table names – adjust if your Supabase schema uses different names.
AUDIT_TABLE = "audit_logs"
CHAT_TABLE = "chat_messages"


def init_db():
    """Placeholder for any required Supabase initialization.
    Supabase client is created in ``app.supabase_client``; no extra steps are
    needed here.
    """
    pass


def init_chat_history():
    """Supabase tables are expected to exist; nothing to initialise.
    This function is kept for compatibility with the startup sequence.
    """
    pass


def save_audit_log(request_id: str, user_message: str, bot_response: str, ttft: float, total_time: float, tokens: int, model_name: str):
    """Insert an audit log record into Supabase safely."""
    try:
        data = {
            "request_id": request_id,
            "user_message": user_message,
            "bot_response": bot_response,
            "ttft": ttft,
            "total_time": total_time,
            "tokens": tokens,
            "model_name": model_name,
        }
        insert(AUDIT_TABLE, data)
    except Exception as e:
        logger.warning(f"No se pudo guardar audit log en Supabase (desconexión o error de red): {e}")


def save_chat_message(session_id: str, role: str, content: str):
    """Insert a chat message into Supabase safely."""
    try:
        data = {
            "session_id": session_id,
            "role": role,
            "content": content,
        }
        insert(CHAT_TABLE, data)
    except Exception as e:
        logger.warning(f"No se pudo guardar mensaje de chat en Supabase (desconexión o error de red): {e}")


def load_chat_history(session_id: str, limit: int = 100):
    """Load recent chat messages for a session safely.
    Returns a list of ``(role, content)`` tuples ordered by insertion.
    """
    try:
        rows = select(CHAT_TABLE, "role, content", session_id=session_id)
        return [(row["role"], row["content"]) for row in rows[:limit]]
    except Exception as e:
        logger.warning(f"No se pudo cargar historial de chat de Supabase: {e}")
        return []
