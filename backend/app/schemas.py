from pydantic import BaseModel
from datetime import date
from typing import Optional, List
class LoginRequest(BaseModel):
    email: str
    password: str
class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    cost_center: str
    is_active: bool = True
    class Config:
        from_attributes = True
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "STAFF"
    cost_center: str = "DC - Surabaya"
class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    cost_center: Optional[str] = None
    is_active: Optional[bool] = None
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
class ProcessRequest(BaseModel):
    vendor: str = "PT Sarana Komputer"
    deskripsi: str = "Pembelian Server Dell R760 (2 unit)"
    subtotal: float = 120000000
    ppn: float = 13200000
    pph: float = 0
    doc_number: str = "NOTA-2026-999"
    tanggal: Optional[date] = None
    threshold: float = 5000000
class ValidationItem(BaseModel):
    name: str
    message: str
    status: str
class ProcessResponse(BaseModel):
    predicted: str
    confidence: float
    reason: str
    coa: str
    total: float
    validations: List[ValidationItem]
class DocumentCreate(BaseModel):
    doc_number: str
    tanggal: date
    jenis: str = "Nota Pengeluaran"
    vendor: str
    deskripsi: str
    subtotal: float = 0
    ppn: float = 0
    pph: float = 0
    total: float = 0
    opex_capex: str = "OPEX"
    coa: str = ""
    cost_center: str = "DC - Surabaya"
    confidence: float = 0.95
    ai_reason: str = ""
    status: str = "Perlu Review"
    po_number: str = "-"
    file_name: str = ""
    ocr_provider: str = "mock-demo"
class DocumentOut(DocumentCreate):
    id: int
    created_by: str = ""
    approved_by: str = ""
    reject_reason: str = ""
    class Config:
        from_attributes = True
class RejectRequest(BaseModel):
    reason: str = ""
