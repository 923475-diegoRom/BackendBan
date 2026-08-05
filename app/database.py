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
