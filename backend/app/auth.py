import os, hashlib, hmac, secrets
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("PRODUCTION: JWT_SECRET wajib di-set di .env, minimal 32 karakter random. Sistem tidak jalan dengan secret default.")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))
security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${h.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(h, check.hex())
    except Exception:
        return False

def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "Belum login. Silakan login dulu.")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(401, "Token tidak valid / kadaluarsa. Silakan login ulang.")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(401, "User tidak ditemukan / nonaktif.")
    return user

def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, f"Akses ditolak. Butuh role: {', '.join(roles)}. Role kamu: {user.role}")
        return user
    return checker

# Matriks approval sesuai dokumen: Finance <=50jt, CFO >50jt & CAPEX besar
def can_approve(user: User, total: float, opex_capex: str) -> tuple[bool, str]:
    if user.role == "CFO":
        return True, "CFO dapat approve semua nilai."
    if user.role == "FINANCE":
        if total <= 50000000:
            return True, "Finance dapat approve sampai Rp 50 jt."
        return False, "Nilai > Rp 50 jt harus di-approve CFO."
    if user.role == "STAFF":
        return False, "Staff tidak dapat approve. Hanya upload & ajukan."
    if user.role == "ADMIN":
        return True, "Admin dapat approve (untuk demo)."
    return False, "Role tidak diizinkan approve."


# === KELOLA AKUN: HANYA CFO ===
# Aturan bisnis: yang bisa create akun & edit privilege pengguna lain hanya CFO.
# Staff & Finance tidak bisa create akun, tidak bisa edit privilege.
# Admin juga tidak bisa (sesuai permintaan: hanya CFO). Jika butuh Admin bisa, ubah require_role di main.py.
def require_cfo():
    # Shortcut: sama dengan require_role("CFO")
    return require_role("CFO")

def can_manage_users(user: User) -> bool:
    return user.role == "CFO"
