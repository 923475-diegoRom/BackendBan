"""Utility functions for interacting with Supabase.

Provides thin wrappers around the Supabase client for common operations
such as selecting, inserting, and updating records. This helps keep the
business logic modules clean and avoids repetitive code.
"""

from supabase import Client
from app.supabase_client import supabase


def select(table: str, columns: str = "*", **filters) -> list[dict]:
    """Select rows from a Supabase table.

    Args:
        table: Table name.
        columns: Comma‑separated column list (default "*").
        **filters: Equality filters applied via ``eq``.

    Returns:
        List of dictionaries representing rows.
    """
    query = supabase.from_(table).select(columns)
    for field, value in filters.items():
        query = query.eq(field, value)
    result = query.execute()
    if result.error:
        raise Exception(f"Supabase select error on {table}: {result.error.message}")
    return result.data


def insert(table: str, data: dict) -> dict:
    """Insert a single row into a Supabase table.

    Returns the inserted record.
    """
    result = supabase.from_(table).insert(data).execute()
    if result.error:
        raise Exception(f"Supabase insert error on {table}: {result.error.message}")
    return result.data[0]


def update(table: str, data: dict, **filters) -> None:
    """Update rows in a Supabase table.

    ``filters`` are applied as equality conditions.
    """
    query = supabase.from_(table).update(data)
    for field, value in filters.items():
        query = query.eq(field, value)
    result = query.execute()
    if result.error:
        raise Exception(f"Supabase update error on {table}: {result.error.message}")
