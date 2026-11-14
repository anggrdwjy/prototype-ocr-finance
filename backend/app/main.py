from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
import csv, io
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import time, os
from datetime import date
from .database import Base, engine, get_db
from .models import Document, User
from .schemas import ProcessRequest, ProcessResponse, DocumentCreate, DocumentOut, RejectRequest, LoginRequest, TokenResponse, UserOut, UserCreate, UserUpdate
from .ocr_service import classify_logic, validate_doc
from .ocr_tesseract import extract_document
from .seed import seed_if_empty, SEED
from .auth import hash_password, verify_password, create_token, get_current_user, require_role, can_approve
app = FastAPI(title="AI OCR Finance API", version="2.0.0")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()] or ["http://localhost:3000"]
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])
@app.on_event("startup")
def startup():
    for i in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            db = next(get_db())
            seed_if_empty(db)
            db.close()
            print("DB ready")
            break
        except Exception as e:
            print(f"Waiting DB... {e}")
            time.sleep(2)
@app.get("/")
def root():
    return {"status":"ok","service":"ai-ocr-backend","version":"3.0.0-production","ocr_provider": "tesseract-local", "docs":"/docs","health":"/health"}
@app.get("/health")
def health():
    return {"status":"ok","service":"ai-ocr-backend","version":"3.0.0-production","ocr_provider": "tesseract-local", "tesseract_lang": os.getenv("TESSERACT_LANG","ind+eng"), "mode": "offline-local"}
@app.get("/api/health")
def api_health():
    return {"status":"ok","service":"ai-ocr-backend","via":"nginx-proxy","ocr_provider": "tesseract-local"}
# ===== AUTH =====
@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email / password salah.")
    if not user.is_active:
        raise HTTPException(403, "Akun nonaktif.")
    token = create_token(user)
    return {"access_token": token, "token_type": "bearer", "user": user}
@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
@app.get("/api/auth/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(require_role("CFO"))):
    # Daftar pengguna: hanya CFO.
    return db.query(User).order_by(User.id).all()

@app.post("/api/auth/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), user: User = Depends(require_role("CFO"))):
    # Create akun: hanya CFO.
    valid_roles = ["STAFF", "FINANCE", "CFO", "ADMIN"]
    role = payload.role.upper().strip()
    if role not in valid_roles:
        raise HTTPException(400, f"Role tidak valid. Pilih: {', '.join(valid_roles)}")
    email = payload.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(400, "Email tidak valid.")
    if len(payload.password or "") < 6:
        raise HTTPException(400, "Password minimal 6 karakter.")
    if not payload.name or len(payload.name.strip()) < 3:
        raise HTTPException(400, "Nama minimal 3 karakter.")
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(400, f"Email {email} sudah dipakai oleh {existing.name} ({existing.role}).")
    new_user = User(name=payload.name.strip(), email=email, password_hash=hash_password(payload.password), role=role, cost_center=payload.cost_center or "DC - Surabaya", is_active=True)
    db.add(new_user); db.commit(); db.refresh(new_user)
    return new_user

@app.patch("/api/auth/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), user: User = Depends(require_role("CFO"))):
    # Edit privilege: hanya CFO.
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "Pengguna tidak ditemukan.")
    # Proteksi: CFO tidak boleh mengubah role dirinya sendiri jadi non-CFO (agar tidak terkunci)
    if target.id == user.id and payload.role and payload.role.upper().strip() != "CFO":
        raise HTTPException(400, "Tidak bisa mengubah role diri sendiri dari CFO ke role lain. Minta CFO lain yang mengubah.")
    # Proteksi: tidak boleh nonaktifkan diri sendiri
    if target.id == user.id and payload.is_active is False:
        raise HTTPException(400, "Tidak bisa menonaktifkan akun sendiri.")
    # Proteksi: jangan sampai tidak ada CFO aktif tersisa
    if payload.role and payload.role.upper().strip() != "CFO" and target.role == "CFO":
        other_cfo = db.query(User).filter(User.id != target.id, User.role == "CFO", User.is_active == True).count()
        if other_cfo == 0:
            raise HTTPException(400, "Tidak bisa demote CFO terakhir. Harus ada minimal 1 CFO aktif.")
    if payload.is_active is False and target.role == "CFO":
        other_cfo = db.query(User).filter(User.id != target.id, User.role == "CFO", User.is_active == True).count()
        if other_cfo == 0:
            raise HTTPException(400, "Tidak bisa nonaktifkan CFO terakhir. Harus ada minimal 1 CFO aktif.")
    if payload.name is not None and payload.name.strip():
        target.name = payload.name.strip()
    if payload.email is not None and payload.email.strip():
        new_email = payload.email.lower().strip()
        if "@" not in new_email:
            raise HTTPException(400, "Email tidak valid.")
        dup = db.query(User).filter(User.email == new_email, User.id != target.id).first()
        if dup:
            raise HTTPException(400, f"Email {new_email} sudah dipakai.")
        target.email = new_email
    if payload.role is not None:
        role = payload.role.upper().strip()
        if role not in ["STAFF", "FINANCE", "CFO", "ADMIN"]:
            raise HTTPException(400, "Role tidak valid.")
        target.role = role
    if payload.cost_center is not None:
        target.cost_center = payload.cost_center
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.password is not None and payload.password != "":
        if len(payload.password) < 6:
            raise HTTPException(400, "Password baru minimal 6 karakter.")
        target.password_hash = hash_password(payload.password)
    db.commit(); db.refresh(target)
    return target

@app.delete("/api/auth/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("CFO"))):
    # Hapus akun: hanya CFO.
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "Pengguna tidak ditemukan.")
    if target.id == user.id:
        raise HTTPException(400, "Tidak bisa menghapus akun sendiri.")
    if target.role == "CFO":
        other_cfo = db.query(User).filter(User.id != target.id, User.role == "CFO", User.is_active == True).count()
        if other_cfo == 0:
            raise HTTPException(400, "Tidak bisa menghapus CFO terakhir.")
    info = {"id": target.id, "name": target.name, "email": target.email, "role": target.role}
    db.delete(target); db.commit()
    return {"status": "deleted", "deleted_by": f"{user.name} (CFO)", **info}
# ===== DOCUMENTS (semua butuh login) =====
@app.get("/api/documents", response_model=List[DocumentOut])
def list_documents(status: Optional[str]=None, opex_capex: Optional[str]=None, q: Optional[str]=None, db: Session=Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Document)
    if status: query = query.filter(Document.status==status)
    if opex_capex: query = query.filter(Document.opex_capex==opex_capex)
    if q: query = query.filter(Document.vendor.ilike(f"%{q}%") | Document.deskripsi.ilike(f"%{q}%") | Document.doc_number.ilike(f"%{q}%"))
    return query.order_by(Document.tanggal.desc()).all()
@app.get("/api/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session=Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id==doc_id).first()
    if not doc: raise HTTPException(404, "Dokumen tidak ditemukan")
    return doc
@app.post("/api/documents/process", response_model=ProcessResponse)
def process_ocr(req: ProcessRequest, db: Session=Depends(get_db), user: User = Depends(get_current_user)):
    total = req.subtotal + req.ppn - req.pph
    predicted, conf, reason, coa = classify_logic(req.deskripsi, total, req.threshold)
    existing = [{"vendor":d.vendor,"total":d.total,"doc_number":d.doc_number} for d in db.query(Document).all()]
    validations = validate_doc({"subtotal":req.subtotal,"ppn":req.ppn,"pph":req.pph,"total":total,"deskripsi":req.deskripsi,"vendor":req.vendor,"doc_number":req.doc_number,"opex_capex":predicted}, existing)
    return {"predicted":predicted,"confidence":conf,"reason":reason,"coa":coa,"total":total,"validations":validations}
@app.post("/api/documents/upload-ocr")
async def upload_ocr(file: UploadFile = File(...), db: Session=Depends(get_db), user: User = Depends(get_current_user)):
    content = await file.read()
    if len(content) > 20*1024*1024:
        raise HTTPException(400, "File terlalu besar. Maksimal 20 MB.")
    try:
        extracted, provider = extract_document(content, file.filename)
    except Exception as e:
        raise HTTPException(400, f"OCR gagal: {e}")
    subtotal, ppn, pph = extracted.get("subtotal",0), extracted.get("ppn",0), extracted.get("pph",0)
    total = extracted.get("total",0) or (subtotal + ppn - pph)
    predicted, conf, reason, coa = classify_logic(extracted.get("deskripsi",""), total, 5000000)
    # confidence gabungan: OCR confidence * klasifikasi confidence
    ocr_conf = extracted.get("confidence", 0.9)
    final_conf = round(float(ocr_conf) * 0.5 + float(conf) * 0.5, 3)
    existing = [{"vendor":d.vendor,"total":d.total,"doc_number":d.doc_number} for d in db.query(Document).all()]
    validations = validate_doc({"subtotal":subtotal,"ppn":ppn,"pph":pph,"total":total,"deskripsi":extracted.get("deskripsi",""),"vendor":extracted.get("vendor",""),"doc_number":extracted.get("doc_number",""),"opex_capex":predicted}, existing)
    return {"file_name": file.filename, "size": len(content), "ocr_provider": provider, "extracted": extracted, "total": total, "predicted": predicted, "confidence": final_conf, "ocr_confidence": ocr_conf, "reason": reason, "coa": coa, "validations": validations, "uploaded_by": user.email}
@app.post("/api/documents", response_model=DocumentOut, status_code=201)
def create_document(payload: DocumentCreate, db: Session=Depends(get_db), user: User = Depends(require_role("STAFF","FINANCE","CFO","ADMIN"))):
    # Create: Staff, Finance, CFO, Admin semua boleh create. Delete hanya Finance/CFO/Admin (lihat delete_document).
    existing = db.query(Document).filter(Document.doc_number==payload.doc_number).first()
    if existing: raise HTTPException(400, f"Nomor dokumen {payload.doc_number} sudah ada (duplikasi)")
    doc = Document(**payload.dict())
    doc.created_by = f"{user.name} ({user.role})"
    db.add(doc); db.commit(); db.refresh(doc)
    return doc
@app.post("/api/documents/{doc_id}/approve", response_model=DocumentOut)
def approve(doc_id: int, db: Session=Depends(get_db), user: User = Depends(require_role("FINANCE","CFO","ADMIN"))):
    doc = db.query(Document).filter(Document.id==doc_id).first()
    if not doc: raise HTTPException(404, "Dokumen tidak ditemukan")
    allowed, msg = can_approve(user, doc.total, doc.opex_capex)
    if not allowed:
        raise HTTPException(403, msg)
    doc.status = "Approved"; doc.approved_by = f"{user.name} ({user.role})"; db.commit(); db.refresh(doc); return doc
@app.post("/api/documents/{doc_id}/reject", response_model=DocumentOut)
def reject(doc_id: int, payload: RejectRequest, db: Session=Depends(get_db), user: User = Depends(require_role("FINANCE","CFO","ADMIN"))):
    doc = db.query(Document).filter(Document.id==doc_id).first()
    if not doc: raise HTTPException(404, "Dokumen tidak ditemukan")
    doc.status = "Ditolak"; doc.reject_reason = payload.reason; doc.approved_by = f"{user.name} ({user.role})"; doc.ai_reason = f"Ditolak: {payload.reason} | Sebelumnya: {doc.ai_reason}"; db.commit(); db.refresh(doc); return doc
@app.get("/api/documents/export/csv")
def export_csv(status: Optional[str] = None, opex_capex: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Export CSV keseluruhan - semua role yang login bisa export, Finance/CFO/Admin juga bisa.
    # Filter sama seperti list, jika tidak ada filter -> semua dokumen.
    query = db.query(Document)
    if status: query = query.filter(Document.status == status)
    if opex_capex: query = query.filter(Document.opex_capex == opex_capex)
    if q: query = query.filter(Document.vendor.ilike(f"%{q}%") | Document.deskripsi.ilike(f"%{q}%") | Document.doc_number.ilike(f"%{q}%"))
    docs = query.order_by(Document.tanggal.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","doc_number","tanggal","jenis","vendor","deskripsi","subtotal","ppn","pph","total","opex_capex","coa","cost_center","confidence","ai_reason","status","po_number","file_name","ocr_provider","created_by","approved_by","reject_reason","created_at","updated_at"])
    for d in docs:
        writer.writerow([d.id, d.doc_number, str(d.tanggal) if d.tanggal else "", d.jenis, d.vendor, d.deskripsi, d.subtotal, d.ppn, d.pph, d.total, d.opex_capex, d.coa, d.cost_center, d.confidence, d.ai_reason, d.status, d.po_number, d.file_name, getattr(d, "ocr_provider", ""), getattr(d, "created_by", ""), getattr(d, "approved_by", ""), getattr(d, "reject_reason", ""), str(d.created_at) if d.created_at else "", str(d.updated_at) if d.updated_at else ""])
    output.seek(0)
    filename = f"ai_ocr_finance_export_{date.today().isoformat()}_{user.role.lower()}.csv"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}", "Access-Control-Expose-Headers": "Content-Disposition"})

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("FINANCE", "CFO", "ADMIN"))):
    # Hanya Finance / CFO / Admin yang boleh delete. Staff tidak boleh.
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Dokumen tidak ditemukan")
    info = {"id": doc.id, "doc_number": doc.doc_number, "vendor": doc.vendor, "total": doc.total}
    db.delete(doc); db.commit()
    return {"status": "deleted", "deleted_by": f"{user.name} ({user.role})", **info}


@app.get("/api/dashboard/stats")
def dashboard_stats(db: Session=Depends(get_db), user: User = Depends(get_current_user)):
    def sum_by(cat):
        v = db.query(func.coalesce(func.sum(Document.total),0)).filter(Document.opex_capex==cat).scalar()
        return float(v or 0)
    total_rev, total_opex, total_capex = sum_by("Revenue"), sum_by("OPEX"), sum_by("CAPEX")
    need_review = db.query(Document).filter(Document.status.in_(["Perlu Review","Menunggu Approval"])).count()
    total_docs = db.query(Document).count()
    cc = db.query(Document.cost_center, func.sum(Document.total).label("total")).group_by(Document.cost_center).all()
    opex_coa = db.query(Document.coa, func.sum(Document.total).label("total")).filter(Document.opex_capex=="OPEX").group_by(Document.coa).all()
    capex_coa = db.query(Document.coa, func.sum(Document.total).label("total")).filter(Document.opex_capex=="CAPEX").group_by(Document.coa).all()
    return {"total_revenue":total_rev,"total_opex":total_opex,"total_capex":total_capex,"need_review":need_review,"total_docs":total_docs,"stp_rate":70,"by_cost_center":[{"cost_center":c,"total":float(t)} for c,t in cc],"opex_by_coa":[{"coa":c,"total":float(t)} for c,t in opex_coa],"capex_by_coa":[{"coa":c,"total":float(t)} for c,t in capex_coa]}
@app.get("/api/reports/opex-capex")
def report(db: Session=Depends(get_db), user: User = Depends(get_current_user)):
    docs = db.query(Document).filter(Document.opex_capex=="CAPEX").all()
    dep = [{"aset":d.deskripsi,"doc_number":d.doc_number,"nilai":d.total,"per_bulan":round(d.total/48,2),"umur_bulan":48,"mulai":str(d.tanggal)} for d in docs]
    return {"capex_depreciation":dep}
