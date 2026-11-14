# MOCK AI - ganti ke Azure Document Intelligence / Google Document AI di produksi
from typing import Tuple, List, Dict
THRESHOLD_DEFAULT = 5000000
def format_rp(x: float) -> str:
    return f"Rp {x:,.0f}".replace(",", ".")
def classify_logic(deskripsi: str, total: float, threshold: float = THRESHOLD_DEFAULT) -> Tuple[str, float, str, str]:
    d = deskripsi.lower()
    capex_keywords = ["server", "ups", "fiber", "genset", "baterai ups", "kabel fiber", "rack baru", "cooling", "cr ac", "pembelian", "pengadaan"]
    opex_keywords = ["listrik", "service rutin", "atk", "perjalanan", "sewa", "catering", "gaji", "internet bulanan", "maintenance rutin"]
    if any(k in d for k in capex_keywords):
        if total >= threshold:
            coa = "1510 - Aset Tetap Peralatan IT" if "server" in d else "1520 - Aset Jaringan / Peralatan DC"
            return "CAPEX", 0.96, f"Mengandung kata kunci aset + nilai {format_rp(total)} >= threshold {format_rp(threshold)} + manfaat > 1 tahun", coa
        else:
            return "OPEX", 0.88, "Kata kunci aset tapi nilai di bawah threshold kapitalisasi", "6130 - Beban Operasional"
    if any(k in d for k in opex_keywords):
        coa = "6110 - Beban Listrik & Utilitas" if "listrik" in d else "6120 - Beban Maintenance" if "service" in d else "6130 - Beban Operasional"
        return "OPEX", 0.95, "Beban operasional periodik, manfaat < 1 tahun", coa
    if total >= 50000000:
        return "CAPEX", 0.82, "Nilai besar, kemungkinan aset — perlu review Finance", "1510 - Aset Tetap Peralatan IT"
    return "OPEX", 0.84, "Tidak ada indikasi aset, diklasifikasikan sebagai beban operasional", "6130 - Beban Operasional"
def validate_doc(doc: Dict, existing_docs: List[Dict]) -> List[Dict]:
    checks = []
    subtotal, ppn, pph, total = doc.get("subtotal",0), doc.get("ppn",0), doc.get("pph",0), doc.get("total",0)
    deskripsi = doc.get("deskripsi","")
    expected_ppn = round(subtotal * 0.11)
    if ppn == 0 and "perjalanan" in deskripsi.lower():
        checks.append({"name":"PPN","message":"SKIP - Non-PKP / tanpa PPN","status":"ok"})
    elif abs(ppn - expected_ppn) <= 1:
        checks.append({"name":"PPN 11%","message":f"Benar: {format_rp(ppn)} = 11% x DPP","status":"ok"})
    else:
        checks.append({"name":"PPN 11%","message":f"SALAH: Harusnya {format_rp(expected_ppn)}, terbaca {format_rp(ppn)}","status":"fail"})
    expected_total = subtotal + ppn - pph
    if abs(expected_total - total) <= 1:
        checks.append({"name":"Total","message":f"Benar: {format_rp(total)} = Subtotal + PPN - PPh","status":"ok"})
    else:
        checks.append({"name":"Total","message":f"SALAH: Harusnya {format_rp(expected_total)}, terbaca {format_rp(total)}","status":"fail"})
    dup = [d for d in existing_docs if d.get("vendor")==doc.get("vendor") and d.get("total")==total and d.get("doc_number")!=doc.get("doc_number")]
    if not dup:
        checks.append({"name":"Duplikasi","message":"Tidak ada dokumen duplikat","status":"ok"})
    else:
        checks.append({"name":"Duplikasi","message":f"BAHAYA: Mirip dengan {dup[0].get('doc_number')}","status":"fail"})
    if total > 80000000:
        checks.append({"name":"Budget","message":"Nilai besar > Rp 80 jt - butuh approval tambahan (CFO)","status":"warn"})
    else:
        checks.append({"name":"Budget","message":"Dalam batas budget Cost Center","status":"ok"})
    if doc.get("opex_capex")=="CAPEX" and total >= 5000000:
        checks.append({"name":"Threshold CAPEX","message":"Di atas threshold, layak dikapitalisasi","status":"ok"})
    elif doc.get("opex_capex")=="OPEX":
        checks.append({"name":"Threshold","message":"OPEX - tidak perlu kapitalisasi","status":"ok"})
    if abs(total - 5000000) / 5000000 < 0.2:
        checks.append({"name":"Review Threshold","message":"Nilai dekat threshold ±20% - wajib review Finance","status":"warn"})
    return checks
def mock_ocr_from_file(filename: str, file_bytes: bytes) -> Dict:
    name = filename.lower()
    if "server" in name:
        return {"vendor":"PT Sarana Komputer","deskripsi":"Pembelian Server Dell R760 (2 unit)","subtotal":120000000,"ppn":13200000,"pph":0}
    if "listrik" in name:
        return {"vendor":"PT Daya Listrik","deskripsi":"Listrik Datacenter Oktober 2026","subtotal":78500000,"ppn":8635000,"pph":0}
    if "genset" in name or "service" in name:
        return {"vendor":"CV Teknik Sejuk","deskripsi":"Service Rutin Genset + Ganti Oli","subtotal":3200000,"ppn":352000,"pph":64000}
    if "fiber" in name:
        return {"vendor":"PT Fiber Optik Nusantara","deskripsi":"Tarik Kabel Fiber Baru Gedung A-B","subtotal":60000000,"ppn":6600000,"pph":1200000}
    return {"vendor":"Vendor dari Scan","deskripsi":"Nota Pengeluaran - Hasil Scan OCR","subtotal":5000000,"ppn":550000,"pph":0}
