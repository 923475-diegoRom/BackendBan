import os
import sqlitecloud
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    db_url = os.getenv("SQLITE_CLOUD_URL")
    if not db_url:
        return None
    try:
        # Some connection strings might have quotes, strip them
        db_url = db_url.strip('"').strip("'")
        return sqlitecloud.connect(db_url)
    except Exception as e:
        print(f"Error connecting to SQLite Cloud: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT,
                    user_message TEXT,
                    bot_response TEXT,
                    ttft REAL,
                    total_time REAL,
                    tokens INTEGER,
                    model_name TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # sqlitecloud python doesn't strictly need commit for some DDL, but good practice
            conn.commit()
        except Exception as e:
            print(f"Error initializing SQLite Cloud DB: {e}")
        finally:
            conn.close()

def save_audit_log(request_id: str, user_message: str, bot_response: str, ttft: float, total_time: float, tokens: int, model_name: str):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO audit_logs (request_id, user_message, bot_response, ttft, total_time, tokens, model_name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (request_id, user_message, bot_response, ttft, total_time, tokens, model_name))
            conn.commit()
        except Exception as e:
            print(f"Error saving audit log to SQLite Cloud: {e}")
        finally:
            conn.close()

# ---------------------------------------------------------------------------
# Chat History Persistence
# ---------------------------------------------------------------------------
# The audit_logs table already records a request/response pair, but for a richer
# conversational UI we need a finer‑grained per‑turn storage. We create a new
# `chat_messages` table that stores each message (user, assistant, or system)
# together with a `session_id` that groups messages belonging to the same
# conversation.

def init_chat_history():
    """Create the `chat_messages` table if it does not exist.

    Columns:
        id          – primary key
        session_id  – identifier for the conversation (string)
        role        – 'user', 'assistant' or 'system'
        content     – raw text of the message
        timestamp   – creation time (default now)
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT CHECK(role IN ('user','assistant','system')) NOT NULL,
                    content TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
        finally:
            conn.close()

def save_chat_message(session_id: str, role: str, content: str):
    """Persist a single message in the `chat_messages` table.

    Args:
        session_id: Identifier that groups messages belonging to the same chat.
        role:       One of 'user', 'assistant', or 'system'.
        content:    The textual content of the message.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content)
            )
            conn.commit()
        finally:
            conn.close()

def load_chat_history(session_id: str, limit: int = 100):
    """Retrieve ordered messages for a given `session_id`.

    Returns a list of tuples `(role, content)` ordered by insertion time.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, limit)
            )
            return cur.fetchall()
        finally:
            conn.close()
        
# ---------------------------------------------------------------------------
