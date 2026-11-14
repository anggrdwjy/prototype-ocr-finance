"""Production seed: TIDAK ada akun demo, TIDAK ada dokumen demo.
Pada first run, sistem hanya membuat akun CFO awal dari environment:
  INIT_CFO_NAME, INIT_CFO_EMAIL, INIT_CFO_PASSWORD
Jika env tidak diisi, tidak ada user yang dibuat — buat CFO pertama
via env atau via database, lalu CFO tersebut yang buat akun lain.
"""
import os
from sqlalchemy.orm import Session
from .models import User
from .auth import hash_password

# SEED dokumen dikosongkan untuk production. Jangan isi data demo.
SEED = []
SEED_USERS = []

def seed_if_empty(db: Session):
    if db.query(User).count() > 0:
        return
    name = os.getenv("INIT_CFO_NAME", "").strip()
    email = os.getenv("INIT_CFO_EMAIL", "").strip().lower()
    password = os.getenv("INIT_CFO_PASSWORD", "").strip()
    if not email or not password:
        print("PRODUCTION: Tidak ada user. Set INIT_CFO_EMAIL & INIT_CFO_PASSWORD di .env untuk membuat CFO pertama.")
        return
    if len(password) < 8:
        print("PRODUCTION: INIT_CFO_PASSWORD minimal 8 karakter. CFO tidak dibuat.")
        return
    db.add(User(name=name or "CFO", email=email, password_hash=hash_password(password), role="CFO", cost_center="Finance", is_active=True))
    db.commit()
    print(f"PRODUCTION: CFO awal dibuat: {email}")
