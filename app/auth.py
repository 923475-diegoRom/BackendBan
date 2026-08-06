import random
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.supabase_client import supabase
from app.supabase_helper import select

router = APIRouter()

security = HTTPBearer()

class SignUpRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserProfile(BaseModel):
    id: str
    name: str
    balance: int
    card: dict
    contacts: list

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        res = supabase.auth.get_user(token)
        if not res or not hasattr(res, 'user') or not res.user:
            raise HTTPException(status_code=401, detail="Token inválido o expirado")
        return res.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Error al verificar token: {str(e)}")

def _get_existing_user_or_fallback():
    users = select("users", "*")
    if users:
        return random.choice(users)
    raise HTTPException(status_code=500, detail="No hay usuarios registrados previamente en la base de datos.")

@router.post("/signup")
def signup(payload: SignUpRequest):
    # Asignar un registro bancario existente aleatorio en lugar de crear uno nuevo dummy
    existing_user = _get_existing_user_or_fallback()
    user_id = existing_user["id"]

    # Registrar en Supabase Auth con el email/password enlazado al perfil existente
    try:
        sign_up_resp = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
            "options": {
                "data": {
                    "profile_id": user_id,
                    "name": existing_user.get("name", payload.name)
                }
            }
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al registrarse en Supabase: {str(e)}")

    if not sign_up_resp.user:
        raise HTTPException(status_code=500, detail="No se pudo crear el usuario en Supabase Auth")

    token = sign_up_resp.session.access_token if sign_up_resp.session else None

    return {
        "access_token": token,
        "message": "Registro exitoso en Supabase" if token else "Registro exitoso. Revisa tu correo si Supabase requiere confirmación.",
        "user": existing_user
    }

@router.post("/login")
def login(payload: LoginRequest):
    try:
        login_resp = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Credenciales incorrectas o error al iniciar sesión: {str(e)}")

    if not login_resp.session:
        raise HTTPException(status_code=401, detail="Inicio de sesión fallido, no se generó sesión activa.")

    user = login_resp.user
    metadata = getattr(user, "user_metadata", {}) or {}
    profile_id = metadata.get("profile_id")

    return {
        "access_token": login_resp.session.access_token,
        "user_id": user.id if user else None,
        "profile_id": profile_id
    }

@router.get("/me", response_model=UserProfile)
def get_me(user=Depends(verify_token)):
    metadata = getattr(user, "user_metadata", {}) or {}
    profile_id = metadata.get("profile_id") if isinstance(metadata, dict) else None

    if not profile_id:
        existing_user = _get_existing_user_or_fallback()
        profile_id = existing_user["id"]

    u_res = supabase.table("users").select("*").eq("id", profile_id).execute()
    if not u_res.data or len(u_res.data) == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user_data = u_res.data[0]

    card_res = supabase.table("cards").select("*").eq("user_id", profile_id).execute()
    card = card_res.data[0] if card_res.data and len(card_res.data) > 0 else {}

    contacts_res = supabase.table("contacts").select("*").eq("user_id", profile_id).execute()
    contacts = contacts_res.data if contacts_res.data else []

    return {
        "id": user_data["id"],
        "name": user_data["name"],
        "balance": user_data["balance"],
        "card": card,
        "contacts": contacts,
    }

