from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, Boolean
from sqlalchemy.sql import func
from .database import Base
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(300), nullable=False)
    role = Column(String(20), nullable=False, default="STAFF")  # STAFF / FINANCE / CFO / ADMIN
    cost_center = Column(String(100), default="DC - Surabaya")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    doc_number = Column(String(50), unique=True, index=True, nullable=False)
    tanggal = Column(Date, nullable=False)
    jenis = Column(String(50), default="Nota Pengeluaran")
    vendor = Column(String(200), nullable=False)
    deskripsi = Column(Text, nullable=False)
    subtotal = Column(Float, default=0)
    ppn = Column(Float, default=0)
    pph = Column(Float, default=0)
    total = Column(Float, default=0)
    opex_capex = Column(String(20), default="OPEX")
    coa = Column(String(200), default="")
    cost_center = Column(String(100), default="DC - Surabaya")
    confidence = Column(Float, default=0.95)
    ai_reason = Column(Text, default="")
    status = Column(String(50), default="Perlu Review")
    po_number = Column(String(50), default="-")
    file_name = Column(String(300), default="")
    ocr_provider = Column(String(50), default="mock-demo")
    created_by = Column(String(150), default="")
    approved_by = Column(String(150), default="")
    reject_reason = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
