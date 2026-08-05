from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uuid
from app.supabase_client import supabase, create_user, create_card, create_contact
from faker import Faker

router = APIRouter()

security = HTTPBearer()

fake = Faker()

class SignUpRequest(BaseModel):
    name: str

class UserProfile(BaseModel):
    id: str
    name: str
    balance: int
    card: dict
    contacts: list

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    resp = supabase.auth.api.get_user(token)
    if resp.error:
        raise HTTPException(status_code=401, detail="Invalid token")
    return resp.user

@router.post("/signup")
def signup(payload: SignUpRequest):
    user = create_user(payload.name)
    user_id = user["id"] if isinstance(user, dict) else user.get("id")
    create_card(user_id)
    contacts = []
    for _ in range(3):
        contact_name = fake.name()
        contact_phone = fake.phone_number()
        contacts.append(create_contact(user_id, contact_name, contact_phone))
    dummy_email = f"{uuid.uuid4().hex[:8]}@example.com"
    sign_up_resp = supabase.auth.sign_up(email=dummy_email, password=uuid.uuid4().hex)
    if sign_up_resp.error:
        raise HTTPException(status_code=500, detail="Failed to generate auth token")
    supabase.auth.api.update_user(sign_up_resp.user.id, data={"user_metadata": {"profile_id": user_id}})
    return {"access_token": sign_up_resp.session.access_token, "user": user}

@router.get("/me", response_model=UserProfile)
def get_me(user=Depends(verify_token)):
    profile_id = user.user_metadata.get("profile_id") if hasattr(user, "user_metadata") else None
    if not profile_id:
        raise HTTPException(status_code=404, detail="Profile not linked")
    u_res = supabase.table("users").select("*").eq("id", profile_id).single().execute()
    if u_res.error:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = u_res.data
    card_res = supabase.table("cards").select("*").eq("user_id", profile_id).single().execute()
    card = card_res.data if not card_res.error else None
    contacts_res = supabase.table("contacts").select("*").eq("user_id", profile_id).execute()
    contacts = contacts_res.data if not contacts_res.error else []
    return {
        "id": user_data["id"],
        "name": user_data["name"],
        "balance": user_data["balance"],
        "card": card,
        "contacts": contacts,
    }
