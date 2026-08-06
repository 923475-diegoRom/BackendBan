import random
import uuid
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

def _create_new_user_profile(name: str):
    """Crea un perfil de usuario nuevo en Supabase con su cuenta, tarjeta y contactos iniciales."""
    user_id = str(uuid.uuid4())
    
    # 1. Insertar nuevo usuario en la tabla 'users' (id es de tipo UUID)
    new_user = {
        "id": user_id,
        "name": name,
        "balance": 100000  # Saldo inicial de $100,000 MXN
    }
    supabase.table("users").insert(new_user).execute()

    # 2. Generar tarjeta Banorte asociada
    card_number = f"4152 31{random.randint(10, 99)} {random.randint(1000, 9999)} {random.randint(1000, 9999)}"
    new_card = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "provider": "Banorte",
        "card_number": card_number,
        "expiry": "12/28"
    }
    try:
        supabase.table("cards").insert(new_card).execute()
    except Exception as e:
        print(f"Warning inserting card: {e}")

    # 3. Insertar contactos de transferencia por defecto
    default_contacts = [
        {"id": str(uuid.uuid4()), "user_id": user_id, "name": "Servicio de Renta", "cuenta_destino": "0012398412"},
        {"id": str(uuid.uuid4()), "user_id": user_id, "name": "Mamá", "cuenta_destino": "0098765432"},
    ]
    try:
        supabase.table("contacts").insert(default_contacts).execute()
    except Exception as e:
        print(f"Warning inserting contacts: {e}")

    return new_user

@router.post("/signup")
def signup(payload: SignUpRequest):
    # Crear un nuevo registro bancario propio para este usuario
    try:
        new_user = _create_new_user_profile(payload.name)
        user_id = new_user["id"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear perfil bancario: {str(e)}")

    # Registrar en Supabase Auth con el email/password enlazado al perfil recién creado
    try:
        sign_up_resp = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
            "options": {
                "email_redirect_to": "https://front-end-ban.vercel.app/",
                "data": {
                    "profile_id": user_id,
                    "name": payload.name
                }
            }
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al registrarse en Supabase Auth: {str(e)}")

    if not sign_up_resp.user:
        raise HTTPException(status_code=500, detail="No se pudo crear el usuario en Supabase Auth")

    token = sign_up_resp.session.access_token if sign_up_resp.session else None

    return {
        "access_token": token,
        "message": "Registro exitoso en Supabase" if token else "Registro exitoso.",
        "user": new_user
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
        user_name = metadata.get("name", "Usuario Banorte") if isinstance(metadata, dict) else "Usuario Banorte"
        new_user = _create_new_user_profile(user_name)
        profile_id = new_user["id"]

    u_res = supabase.table("users").select("*").eq("id", profile_id).execute()
    if not u_res.data or len(u_res.data) == 0:
        # Si el profile_id no existe en la BD, creamos uno nuevo
        user_name = metadata.get("name", "Usuario Banorte") if isinstance(metadata, dict) else "Usuario Banorte"
        new_user = _create_new_user_profile(user_name)
        user_data = new_user
        profile_id = new_user["id"]
    else:
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


