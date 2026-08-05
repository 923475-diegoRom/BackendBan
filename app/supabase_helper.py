"""Utility functions for interacting with Supabase.

Provides thin wrappers around the Supabase client for common operations
such as selecting, inserting, and updating records. This helps keep the
business logic modules clean and avoids repetitive code.
"""

from supabase import Client
from app.supabase_client import supabase


def select(table: str, columns: str = "*", **filters) -> list[dict]:
    query = supabase.from_(table).select(columns)
    for field, value in filters.items():
        query = query.eq(field, value)
    result = query.execute()
    return result.data if result.data else []


def insert(table: str, data: dict) -> dict:
    result = supabase.from_(table).insert(data).execute()
    if not result.data:
        raise Exception(f"Supabase insert error on {table}: no data returned")
    return result.data[0]


def update(table: str, data: dict, **filters) -> None:
    query = supabase.from_(table).update(data)
    for field, value in filters.items():
        query = query.eq(field, value)
    query.execute()
