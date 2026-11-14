# AI OCR Finance — Production

Sistem pencatatan invoice & nota pengeluaran: foto nota → OCR → klasifikasi OPEX / CAPEX → validasi → approval → laporan + export CSV.

## Jalankan

```bash
cp .env.example .env   # isi JWT_SECRET, POSTGRES_PASSWORD, INIT_CFO_*
docker compose up --build
```

- Frontend: http://localhost:3000
- Health: http://localhost:8000/health

CFO pertama dibuat otomatis dari `INIT_CFO_EMAIL` / `INIT_CFO_PASSWORD` saat DB masih kosong. Setelah login, hapus nilai tersebut dari `.env` dan buat akun lain lewat menu **Kelola Akun**.

## Role

| Role | Buat Dokumen | Hapus Dokumen | Approve | Buat Akun / Edit Privilege |
|------|--------------|---------------|---------|----------------------------|
| Staff | ✅ | ❌ | ❌ | ❌ |
| Finance | ✅ | ✅ | ✅ ≤ Rp 50 jt | ❌ |
| CFO | ✅ | ✅ | ✅ Semua | ✅ Hanya CFO |
| Admin | ✅ | ✅ | ✅ Semua | ❌ |

- Finance > Rp 50 jt harus CFO.
- CFO tidak bisa hapus / demote dirinya sendiri. Minimal 1 CFO aktif dijaga.

## Fitur

- **OCR:** Tesseract lokal (offline). Foto tidak keluar server. JPG / PNG / PDF, maks 20 MB.
- **Klasifikasi:** OPEX / CAPEX + CoA, bisa dikoreksi manual. Validasi PPN 11%, total, duplikasi, budget.
- **Depresiasi CAPEX:** Nilai ÷ 48 bulan.
- **Export CSV:** Dashboard & Laporan → Export CSV Keseluruhan (24 kolom).
- **Kelola Akun (CFO):** Buat akun, edit role, reset password, aktif/nonaktif, hapus akun.

## Struktur

```
├── docker-compose.yml
├── .env.example
├── db/init.sql
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py        # API
│       ├── auth.py        # JWT + role
│       ├── models.py      # User + Document
│       ├── schemas.py
│       ├── ocr_tesseract.py  # OCR
│       ├── ocr_service.py    # Klasifikasi + validasi
│       ├── database.py
│       └── seed.py        # CFO pertama dari env
└── frontend/
    ├── Dockerfile
    ├── nginx.conf       # Proxy /api/ → backend
    └── src/
        ├── App.jsx
        ├── api.js
        └── index.css
```

## Catatan Production

- `JWT_SECRET` wajib min 32 karakter, jangan pakai nilai contoh.
- `CORS_ORIGINS` isi domain frontend production.
- Jangan commit `.env`. Backup volume `postgres_data` berkala.
- Foto harus tegak & terang agar OCR akurat. Koreksi hasil OCR sebelum simpan.

## Dokumen Bisnis

Lihat `PRG_AI_OCR_Finance_Production.docx` untuk requirement lengkap.
# prototype-ocr-finance
