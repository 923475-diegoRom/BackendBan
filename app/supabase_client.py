import os
import uuid
from supabase import create_client, Client

raw_url = os.getenv("SUPABASE_URL", "")
SUPABASE_URL = raw_url.replace("/rest/v1/", "").replace("/rest/v1", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Service role client for privileged server‑side operations
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def create_user(name: str, initial_balance: int = 1_000_000):
    """Insert a new user into the `users` table and return the record.
    """
    data = {
        "name": name,
        "balance": initial_balance,
    }
    result = supabase.table("users").insert(data).execute()
    if not result.data:
        raise Exception("Supabase error creating user: no data returned")
    return result.data[0]

def create_card(user_id: str, provider: str = "Banorte", card_number: str | None = None, expiry: str | None = None):
    """Create a Banorte card for the given user.
    """
    if not card_number:
        card_number = f"{user_id[:4].upper()}{int(uuid.uuid4().int >> 96):010d}"
    if not expiry:
        expiry = "2029-12-31"
    data = {
        "user_id": user_id,
        "provider": provider,
        "card_number": card_number,
        "expiry": expiry,
    }
    result = supabase.table("cards").insert(data).execute()
    if not result.data:
        raise Exception("Supabase error creating card: no data returned")
    return result.data[0]

def create_contact(user_id: str, name: str, phone: str):
    """Add a contact linked to a user.
    """
    data = {
        "user_id": user_id,
        "name": name,
        "phone": phone,
    }
    result = supabase.table("contacts").insert(data).execute()
    if not result.data:
        raise Exception("Supabase error creating contact: no data returned")
    return result.data[0]
