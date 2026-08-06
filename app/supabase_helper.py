"""Utility functions for interacting with Supabase.

Provides thin wrappers around the Supabase client for common operations
such as selecting, inserting, and updating records. This helps keep the
business logic modules clean and avoids repetitive code.
"""

from supabase import Client
from app.supabase_client import supabase
import logging

logger = logging.getLogger("BanorteGenAI")


def select(table: str, columns: str = "*", **filters) -> list[dict]:
    try:
        query = supabase.from_(table).select(columns)
        for field, value in filters.items():
            query = query.eq(field, value)
        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        logger.warning(f"Reintentando select en Supabase tras fallo de conexion: {e}")
        query = supabase.from_(table).select(columns)
        for field, value in filters.items():
            query = query.eq(field, value)
        result = query.execute()
        return result.data if result.data else []


def insert(table: str, data: dict) -> dict:
    try:
        result = supabase.from_(table).insert(data).execute()
        if not result.data:
            raise Exception(f"Supabase insert error on {table}: no data returned")
        return result.data[0]
    except Exception as e:
        logger.warning(f"Reintentando insert en Supabase tras fallo de conexion ({e})")
        result = supabase.from_(table).insert(data).execute()
        if not result.data:
            raise Exception(f"Supabase insert error on {table}: no data returned")
        return result.data[0]


def update(table: str, data: dict, **filters) -> None:
    try:
        query = supabase.from_(table).update(data)
        for field, value in filters.items():
            query = query.eq(field, value)
        query.execute()
    except Exception as e:
        logger.warning(f"Reintentando update en Supabase tras fallo de conexion ({e})")
        query = supabase.from_(table).update(data)
        for field, value in filters.items():
            query = query.eq(field, value)
        query.execute()

