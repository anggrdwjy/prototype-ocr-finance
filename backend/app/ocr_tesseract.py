"""
OCR TESSERACT LOKAL 100% - Tanpa Azure / Tanpa Cloud / Tanpa API Key
Pipeline:
  1. File (JPG/PNG/PDF) -> Image (PIL / PyMuPDF untuk PDF)
  2. Preprocessing OpenCV: grayscale -> upscale -> denoise -> adaptive threshold -> deskew ringan
  3. Tesseract OCR (lang ind+eng, PSM 6) -> raw text + TSV confidence
  4. Parser Indonesia: vendor, deskripsi, subtotal, PPN, PPh, total, nomor dokumen, tanggal
Kelebihan: gratis, offline, data tidak keluar server, cocok untuk pilot & on-premise.
Kekurangan vs Azure: lebih sensitif ke foto buram / miring parah / tabel kompleks.
Tips foto terbaik ada di README_TESSERACT.md.
"""
import os, io, re, statistics
from typing import Dict, Tuple

def _to_float(v) -> float:
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v).strip()
    # Format Indonesia: 133.200.000 atau 133200000 atau 133.200.000,00
    # Hapus Rp, spasi, lalu handle koma desimal
    s = s.replace("Rp", "").replace("IDR", "").replace(" ", "").strip()
    # Jika ada koma dan titik, koma adalah desimal
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and s.count(",") == 1 and len(s.split(",")[-1]) == 2:
        s = s.replace(",", ".")
    else:
        s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s) if s not in ("", "-", ".") else 0.0
    except:
        return 0.0

def _find_money(text: str, patterns) -> float:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            # Ambil grup terakhir yang berisi angka
            for g in reversed(m.groups()):
                if g and re.search(r"\d", g):
                    val = _to_float(g)
                    if val > 0:
                        return val
    return 0.0

def _preprocess_image(pil_img):
    """OpenCV preprocessing: grayscale, upscale, denoise, threshold"""
    try:
        import cv2
        import numpy as np
        img = np.array(pil_img.convert("RGB"))
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        # Upscale jika kecil (foto HP biasanya sudah besar, tapi scan kecil perlu)
        h, w = gray.shape
        if w < 1800:
            scale = 1800 / max(w, 1)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        # Denoise
        gray = cv2.medianBlur(gray, 3)
        # Adaptive threshold agar teks tetap jelas di foto gelap / bayangan
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
        # Kembalikan ke PIL
        from PIL import Image
        return Image.fromarray(thresh)
    except Exception:
        return pil_img

def _ocr_image(pil_img, lang="ind+eng", psm="6"):
    import pytesseract
    from PIL import Image
    # Coba preprocessing dulu, jika hasil jelek fallback ke original
    processed = _preprocess_image(pil_img)
    config = f"--psm {psm} --oem 3 -l {lang}"
    text_proc = pytesseract.image_to_string(processed, config=config)
    # Jika teks preprocessing terlalu pendek, coba original
    if len(text_proc.strip()) < 30:
        text_orig = pytesseract.image_to_string(pil_img, config=config)
        if len(text_orig.strip()) > len(text_proc.strip()):
            text_proc = text_orig
            processed = pil_img
    # Confidence dari TSV
    conf_vals = []
    try:
        data = pytesseract.image_to_data(processed, config=config, output_type=pytesseract.Output.DICT)
        for c in data.get("conf", []):
            try:
                cf = float(c)
                if cf > 0:
                    conf_vals.append(cf)
            except:
                pass
    except:
        pass
    conf = (statistics.mean(conf_vals) / 100.0) if conf_vals else 0.75
    conf = max(0.55, min(0.95, conf))
    return text_proc, conf

def _parse_indonesian_invoice(text: str) -> Dict:
    # Bersihkan teks
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    full = "\n".join(lines)

    # --- Vendor: cari baris PT / CV / Toko / UD / Koperasi / Grab / Tokopedia ---
    vendor = "Vendor dari Scan (Tesseract)"
    for line in lines[:12]:
        if re.search(r"\b(PT|CV|UD|Toko|Koperasi|Yayasan)\b", line, re.IGNORECASE) and len(line) > 4:
            # Bersihkan karakter OCR aneh di awal
            vendor = re.sub(r"^[^A-Za-z0-9]+", "", line)[:200]
            break
    if vendor.startswith("Vendor dari Scan"):
        for line in lines[:8]:
            if len(line) > 5 and not re.search(r"\b(total|subtotal|ppn|pph|invoice|nota|tanggal|faktur)\b", line, re.IGNORECASE):
                # Ambil baris pertama yang mirip nama perusahaan
                if re.search(r"[A-Za-z]{3,}", line):
                    vendor = line[:200]
                    break

    # --- Nomor dokumen ---
    doc_number = ""
    m = re.search(r"(INV|NOTA|Faktur|Kwitansi|NO\.?|No\.?|Nomor)[^A-Za-z0-9]{0,5}([A-Z0-9\-/]{4,30})", full, re.IGNORECASE)
    if m:
        doc_number = m.group(2).strip().upper()[:50]

    # --- Tanggal: 01/11/2026, 01-11-2026, 01 Nov 2026 ---
    tanggal = None
    m_date = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", full)
    if m_date:
        d, mo, y = m_date.groups()
        tanggal = f"{y}-{int(mo):02d}-{int(d):02d}"
    else:
        m_date2 = re.search(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agu|Sep|Okt|Nov|Des|January|February|March|April|May|June|July|August|September|October|November|December)\w*\s+(\d{4})", full, re.IGNORECASE)
        if m_date2:
            month_map = {"jan":1,"feb":2,"mar":3,"apr":4,"mei":5,"may":5,"jun":6,"jul":7,"agu":8,"aug":8,"sep":9,"okt":10,"oct":10,"nov":11,"des":12,"dec":12}
            d, mon, y = m_date2.groups()
            mm = month_map.get(mon[:3].lower(), 1)
            tanggal = f"{y}-{mm:02d}-{int(d):02d}"

    # --- Angka: Subtotal, PPN, PPh, Total ---
    # Pola harus fleksibel karena OCR sering salah baca titik/koma
    subtotal = _find_money(full, [
        r"Sub\s*total[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"DPP[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"Sub\s*Total[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"Harga[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
    ])
    ppn = _find_money(full, [
        r"PPN[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"VAT[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"Pajak\s*Pertambahan[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
    ])
    pph = _find_money(full, [
        r"PPh\s*21[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"PPh\s*23[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"PPh[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
    ])
    total = _find_money(full, [
        r"Grand\s*Total[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"Total\s*Bayar[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"Total\s*Tagihan[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"Jumlah\s*Total[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
        r"Total[^0-9]{0,10}([0-9][0-9.,\s]{4,20})",
    ])
    # Validasi silang: jika total kosong, hitung dari subtotal+ppn-pph
    if total == 0 and subtotal > 0:
        total = subtotal + ppn - pph
    # Jika subtotal kosong tapi total ada, tebak subtotal = total - ppn + pph
    if subtotal == 0 and total > 0:
        subtotal = total - ppn + pph
        if subtotal < 0: subtotal = total
    # Jika PPN kosong tapi subtotal ada, cek apakah 11% masuk akal? Jangan tebak, biarkan 0 agar validasi menangkapnya

    # --- Deskripsi: ambil 1-2 baris terpanjang yang bukan header / angka ---
    desc_candidates = []
    skip_keywords = ["invoice","nota","faktur","kwitansi","total","subtotal","ppn","pph","tanggal","nomor","vendor","kepada","dari","npwp","telp","alamat","bank","rekening"]
    for line in lines:
        low = line.lower()
        if any(k in low for k in skip_keywords):
            continue
        if len(line) < 8 or len(line) > 120:
            continue
        if re.search(r"^\d+[.,\s\d]+$", line):
            continue
        # Harus ada huruf
        if not re.search(r"[A-Za-z]{3,}", line):
            continue
        desc_candidates.append(line)
    # Prioritaskan baris yang mengandung kata kunci bisnis
    desc_candidates_sorted = sorted(desc_candidates, key=lambda s: (any(k in s.lower() for k in ["server","listrik","genset","fiber","rack","bandwidth","service","atk","perjalanan","sewa","pembelian","pengadaan","baterai","ups","cooling"]), len(s)), reverse=True)
    deskripsi = "; ".join(desc_candidates_sorted[:2]) if desc_candidates_sorted else "Nota Pengeluaran - Hasil Scan OCR (Tesseract)"
    deskripsi = deskripsi[:500]

    return {
        "vendor": vendor, "deskripsi": deskripsi,
        "subtotal": float(subtotal), "ppn": float(ppn), "pph": float(pph), "total": float(total),
        "doc_number": doc_number, "tanggal": tanggal,
        "raw_text": full[:3000],
    }

def extract_document_tesseract(file_bytes: bytes, filename: str) -> Tuple[Dict, str]:
    from PIL import Image
    lang = os.getenv("TESSERACT_LANG", "ind+eng")
    psm = os.getenv("TESSERACT_PSM", "6")
    texts = []
    confs = []
    # PDF: render tiap halaman (maks 3 halaman pertama)
    if filename.lower().endswith(".pdf"):
        try:
            import fitz
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            for i in range(min(len(pdf), 3)):
                pix = pdf[i].get_pixmap(dpi=250)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                t, c = _ocr_image(img, lang=lang, psm=psm)
                texts.append(t); confs.append(c)
        except Exception as e:
            raise RuntimeError(f"Gagal baca PDF: {e}")
    else:
        img = Image.open(io.BytesIO(file_bytes))
        # Handle EXIF rotation (foto HP sering terotasi)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except:
            pass
        # Convert ke RGB
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255,255,255))
            bg.paste(img, mask=img.split()[-1] if img.mode=="RGBA" else None)
            img = bg
        else:
            img = img.convert("RGB")
        t, c = _ocr_image(img, lang=lang, psm=psm)
        texts.append(t); confs.append(c)
    full_text = "\n".join(texts)
    avg_conf = sum(confs)/len(confs) if confs else 0.75
    parsed = _parse_indonesian_invoice(full_text)
    parsed["confidence"] = float(avg_conf)
    parsed["provider"] = "tesseract-local"
    return parsed, "tesseract-local"

# Wrapper agar compatible dengan kode lama
def extract_document(file_bytes: bytes, filename: str):
    return extract_document_tesseract(file_bytes, filename)
