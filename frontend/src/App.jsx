import { useEffect, useState, useRef } from 'react'
import { api, apiUpload, apiExportCsv, fmtRp, getApiBase, getUser, logout } from './api.js'


export default function App(){
  const [user, setUser] = useState(getUser())
  const [loginForm, setLoginForm] = useState({email:'', password:''})
  const [loginError, setLoginError] = useState('')
  const [tab, setTab] = useState('dashboard')
  const [docs, setDocs] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [conn, setConn] = useState('checking')
  const [filter, setFilter] = useState('')
  const [form, setForm] = useState({vendor:'PT Sarana Komputer', deskripsi:'Pembelian Server Dell R760 (2 unit)', subtotal:120000000, ppn:13200000, pph:0, doc_number:'NOTA-2026-999', threshold:5000000})
  const [result, setResult] = useState(null)
  const [uploadInfo, setUploadInfo] = useState(null)
  const [report, setReport] = useState(null)
  const [rejectReason, setRejectReason] = useState('')
  const [usersList, setUsersList] = useState([])
  const [userForm, setUserForm] = useState({name:'', email:'', password:'', role:'STAFF', cost_center:'DC - Surabaya'})
  const [editingUserId, setEditingUserId] = useState(null)
  const [editingUser, setEditingUser] = useState({name:'', email:'', role:'STAFF', cost_center:'DC - Surabaya', is_active:true, password:''})
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({doc_number:'', tanggal: new Date().toISOString().slice(0,10), jenis:'Nota Pengeluaran', vendor:'', deskripsi:'', subtotal:0, ppn:0, pph:0, total:0, opex_capex:'OPEX', coa:'6130 - Beban Operasional', cost_center:'DC - Surabaya', po_number:'-'})
  const fileRef = useRef(null)

  const load = async () => {
    if(!getUser()) return
    try{
      const [d,s] = await Promise.all([api('/api/documents'), api('/api/dashboard/stats')])
      setDocs(d); setStats(s); setConn('ok'); setMsg('')
    }catch(e){ setConn('fail'); setMsg('❌ Gagal fetch: '+e.message) }
  }
  useEffect(()=>{ if(user) load() },[user])

  const doLogin = async (email, password) => {
    setLoginError('')
    try{
      const r = await api('/api/auth/login', {method:'POST', body: JSON.stringify({email: email||loginForm.email, password: password||loginForm.password})})
      localStorage.setItem('ocr_token', r.access_token)
      localStorage.setItem('ocr_user', JSON.stringify(r.user))
      setUser(r.user); setMsg(`Selamat datang, ${r.user.name} (${r.user.role})`)
    }catch(e){ setLoginError(e.message) }
  }

  const process = async () => {
    setLoading(true); setMsg('')
    try{
      const r = await api('/api/documents/process', {method:'POST', body: JSON.stringify({...form, tanggal: new Date().toISOString().slice(0,10)})})
      setResult(r); setUploadInfo(null); setMsg('AI OCR selesai — lihat prediksi & validasi di bawah.')
    }catch(e){ setMsg('Gagal: '+e.message) }
    setLoading(false)
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0]
    if(!file) return
    setLoading(true); setMsg(''); setUploadInfo(null)
    try{
      const fd = new FormData()
      fd.append('file', file)
      const r = await apiUpload('/api/documents/upload-ocr', fd)
      setUploadInfo(r)
      // Isi form otomatis dari hasil OCR real
      setForm(prev => ({...prev, vendor: r.extracted.vendor||prev.vendor, deskripsi: r.extracted.deskripsi||prev.deskripsi, subtotal: r.extracted.subtotal||0, ppn: r.extracted.ppn||0, pph: r.extracted.pph||0, doc_number: r.extracted.doc_number || `SCAN-${Date.now().toString().slice(-6)}`}))
      setResult(r)
      setMsg(`OCR Real selesai via ${r.ocr_provider} — Confidence OCR ${(r.ocr_confidence*100).toFixed(1)}%. Cek & koreksi jika ada yang salah, lalu Simpan.`)
    }catch(err){ setMsg('Gagal OCR: '+err.message) }
    setLoading(false)
    e.target.value = ''
  }

  const saveDoc = async () => {
    if(!result) return
    try{
      await api('/api/documents', {method:'POST', body: JSON.stringify({doc_number: form.doc_number, tanggal: new Date().toISOString().slice(0,10), jenis:'Nota Pengeluaran', vendor: form.vendor, deskripsi: form.deskripsi, subtotal: form.subtotal, ppn: form.ppn, pph: form.pph, total: result.total, opex_capex: result.predicted, coa: result.coa, cost_center:'DC - Surabaya', confidence: result.confidence, ai_reason: result.reason, status: result.confidence>=0.93?'Approved':'Perlu Review', po_number:'PO-2026-999', ocr_provider: uploadInfo?.ocr_provider || 'manual-form'})})
      setMsg('Berhasil disimpan & posting ke Dashboard!'); setResult(null); setUploadInfo(null); load()
    }catch(e){ setMsg('Gagal simpan: '+e.message) }
  }
  const approve = async (id) => { try{ await api(`/api/documents/${id}/approve`,{method:'POST'}); load() }catch(e){ setMsg('Gagal approve: '+e.message) } }
  const reject = async (id) => { if(!rejectReason) return alert('Isi alasan tolak dulu'); try{ await api(`/api/documents/${id}/reject`,{method:'POST', body: JSON.stringify({reason: rejectReason})}); setRejectReason(''); load() }catch(e){ setMsg('Gagal tolak: '+e.message) } }
  const handleExportCsv = async (filterStatus='') => {
        try{
          const qs = filterStatus ? `?status=${encodeURIComponent(filterStatus)}` : ''
          const fname = await apiExportCsv(`/api/documents/export/csv${qs}`, `ai_ocr_export_${new Date().toISOString().slice(0,10)}.csv`)
          setMsg(`Export CSV berhasil: ${fname} — ${docs.length} dokumen (atau sesuai filter).`)
        }catch(e){ setMsg('Gagal export CSV: '+e.message) }
      }
      const handleDelete = async (id, docNumber) => {
        if(!window.confirm(`Hapus dokumen ${docNumber}? Tindakan ini tidak bisa dibatalkan.`)) return
        try{ await api(`/api/documents/${id}`, {method:'DELETE'}); setMsg(`Dokumen ${docNumber} berhasil dihapus.`); load() }catch(e){ setMsg('Gagal hapus: '+e.message) }
      }
      const handleCreateManual = async () => {
        if(!createForm.doc_number || !createForm.vendor || !createForm.deskripsi) return alert('Isi Nomor Dokumen, Vendor, dan Deskripsi dulu.')
        const total = Number(createForm.subtotal) + Number(createForm.ppn) - Number(createForm.pph)
        try{
          await api('/api/documents', {method:'POST', body: JSON.stringify({...createForm, subtotal:Number(createForm.subtotal), ppn:Number(createForm.ppn), pph:Number(createForm.pph), total, confidence:1.0, ai_reason:'Dibuat manual oleh '+user.role, status:'Perlu Review', file_name:'manual-entry'})})
          setMsg(`Dokumen ${createForm.doc_number} berhasil dibuat oleh ${user.role}.`); setShowCreate(false); setCreateForm({doc_number:'', tanggal: new Date().toISOString().slice(0,10), jenis:'Nota Pengeluaran', vendor:'', deskripsi:'', subtotal:0, ppn:0, pph:0, total:0, opex_capex:'OPEX', coa:'6130 - Beban Operasional', cost_center:'DC - Surabaya', po_number:'-' }); load()
        }catch(e){ setMsg('Gagal create: '+e.message) }
      }
      const loadUsers = async () => {
  if(user?.role !== 'CFO') return
  try{ const u = await api('/api/auth/users'); setUsersList(u) }catch(e){ setMsg('Gagal load pengguna: '+e.message) }
}
const createUser = async () => {
  if(user?.role !== 'CFO') return alert('Hanya CFO yang bisa create akun.')
  if(!userForm.name || !userForm.email || !userForm.password) return alert('Isi Nama, Email, dan Password dulu.')
  try{
    const r = await api('/api/auth/users', {method:'POST', body: JSON.stringify(userForm)})
    setMsg(`Akun berhasil dibuat: ${r.name} (${r.email} - ${r.role})`)
    setUserForm({name:'', email:'', password:'', role:'STAFF', cost_center:'DC - Surabaya'})
    loadUsers()
  }catch(e){ setMsg('Gagal create akun: '+e.message) }
}
const startEditUser = (u) => { setEditingUserId(u.id); setEditingUser({name:u.name, email:u.email, role:u.role, cost_center:u.cost_center, is_active:u.is_active, password:''}) }
const saveEditUser = async (id) => {
  try{
    const payload = {name: editingUser.name, email: editingUser.email, role: editingUser.role, cost_center: editingUser.cost_center, is_active: editingUser.is_active}
    if(editingUser.password) payload.password = editingUser.password
    const r = await api(`/api/auth/users/${id}`, {method:'PATCH', body: JSON.stringify(payload)})
    setMsg(`Privilege ${r.name} berhasil diubah jadi ${r.role} (Aktif: ${r.is_active?'Ya':'Tidak'}).`)
    setEditingUserId(null); loadUsers()
  }catch(e){ setMsg('Gagal edit pengguna: '+e.message) }
}
const toggleUserActive = async (u) => {
  try{ await api(`/api/auth/users/${u.id}`, {method:'PATCH', body: JSON.stringify({is_active: !u.is_active})}); setMsg(`${u.name} ${!u.is_active?'diaktifkan':'dinonaktifkan'}.`); loadUsers() }catch(e){ setMsg('Gagal ubah status: '+e.message) }
}
const deleteUser = async (u) => {
  if(!window.confirm(`Hapus akun ${u.name} (${u.email} - ${u.role})? Tindakan ini tidak bisa dibatalkan.`)) return
  try{ await api(`/api/auth/users/${u.id}`, {method:'DELETE'}); setMsg(`Akun ${u.name} berhasil dihapus.`); loadUsers() }catch(e){ setMsg('Gagal hapus akun: '+e.message) }
}
const loadReport = async () => { try{ const r = await api('/api/reports/opex-capex'); setReport(r) }catch(e){ setMsg(e.message) } }
  const filteredDocs = docs.filter(d => !filter || d.status===filter || d.opex_capex===filter)
  const canManageUsersUI = user && user.role === 'CFO'
  const canApproveUI = user && ['FINANCE','CFO','ADMIN'].includes(user.role)
  const canDeleteUI = user && ['FINANCE','CFO','ADMIN'].includes(user.role)
  const canCreateUI = user && ['STAFF','FINANCE','CFO','ADMIN'].includes(user.role)
  const canExportUI = !!user
  const canUploadUI = user && ['STAFF','FINANCE','CFO','ADMIN'].includes(user.role)

  // ===== LOGIN PAGE =====
  if(!user){
    return (
      <div style={{minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'#0F2B46', padding:20}}>
        <div style={{background:'#fff', borderRadius:16, padding:28, maxWidth:440, width:'100%'}}>
          <h1 style={{margin:0}}>🧾 AI OCR Finance</h1>
          <p style={{color:'#64748B'}}>Invoice Revenue & Nota OPEX / CAPEX<br/><b>Tesseract Lokal v2.1</b> — OCR Offline + Login Role</p>
          <label>Email</label><input value={loginForm.email} onChange={e=>setLoginForm({...loginForm, email:e.target.value})} placeholder="nama@perusahaan.id"/>
          <label>Password</label><input type="password" value={loginForm.password} onChange={e=>setLoginForm({...loginForm, password:e.target.value})} placeholder="••••••"/>
          {loginError && <div className="alert fail">{loginError}</div>}
          <button className="primary" onClick={()=>doLogin()} style={{marginTop:10}}>Masuk →</button>
          <div style={{marginTop:14, background:'#F2F5F9', padding:12, borderRadius:10, fontSize:12, color:'#334155'}}>
            <b>Role:</b><br/>• <b>Staff</b> — Upload & ajukan dokumen<br/>• <b>Finance</b> — Approve sampai Rp 50 jt<br/>• <b>CFO</b> — Approve semua nilai<br/>• <b>Admin</b> — Approve semua<br/><br/><b>OCR:</b> Tesseract Lokal 100% Offline — tanpa Azure / API key / internet. Data tidak keluar server.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>🧾 AI OCR Finance</h1><p>Invoice Revenue & Nota OPEX / CAPEX<br/>Tesseract Lokal v2.1 — OCR Offline + Role</p>
        <div style={{background:'#1A3A5A', padding:12, borderRadius:10, fontSize:13}}>
          <b>{user.name}</b><br/><span className="badge" style={{background:'#5079BD', color:'#fff', marginTop:6}}>{user.role}</span><br/>
          <span style={{fontSize:12, color:'#CBD7E6'}}>{user.email}</span><br/>
          <button className="ghost" style={{marginTop:8, width:'100%'}} onClick={logout}>Keluar</button>
        </div>
        <div className="nav">
          <button className={tab==='dashboard'?'active':''} onClick={()=>setTab('dashboard')}>📊 Dashboard</button>
          {canUploadUI && <button className={tab==='upload'?'active':''} onClick={()=>setTab('upload')}>📤 Upload & OCR Tesseract</button>}
          <button className={tab==='approval'?'active':''} onClick={()=>setTab('approval')}>✅ Validasi & Approval</button>
          <button className={tab==='report'?'active':''} onClick={()=>{setTab('report'); loadReport()}}>📈 Laporan OPEX / CAPEX</button>
          <button className={tab==='api'?'active':''} onClick={()=>setTab('api')}>❓ Bantuan</button>
              {canManageUsersUI && <button className={tab==='users'?'active':''} onClick={()=>{setTab('users'); loadUsers()}}>👥 Kelola Akun (CFO)</button>}
              {!canManageUsersUI && <div style={{fontSize:12, color:'#94A3B8', padding:'8px 10px', background:'#1A3A5A', borderRadius:8, marginTop:8}}>🔒 Kelola Akun: hanya CFO<br/><span style={{fontSize:11}}>Staff & Finance tidak bisa create akun.</span></div>}
        </div>
        <div style={{marginTop:16, background: conn==='ok' ? '#0F5132' : conn==='fail' ? '#7A1F1F' : '#1A3A5A', padding:12, borderRadius:10, fontSize:13}}>
          <b>Status Backend:</b> {conn==='ok' ? '🟢 Connected' : conn==='fail' ? '🔴 Gagal Fetch' : '🟡 Checking...'}<br/>
          <span style={{fontSize:12, color:'#CBD7E6'}}>API: {getApiBase()}</span><br/>
          {conn==='fail' && <button className="ghost" style={{marginTop:8, width:'100%'}} onClick={load}>🔄 Coba Lagi</button>}
        </div>
      </aside>
      <main className="main">
        {msg && <div className={msg.startsWith('❌')||msg.startsWith('Gagal') ? 'alert fail' : 'alert ok'}>{msg}</div>}
        {tab==='dashboard' && (
          <>
            <h2>Dashboard Finance — Real-time</h2><p>Halo, <b>{user.name}</b> ({user.role}) — {stats? `${stats.total_docs} dokumen` : ''}</p>
            <div className="kpi-grid">
              <div className="kpi"><small>Invoice Revenue (MTD)</small><b>{fmtRp(stats?.total_revenue||0)}</b><span>📈 +12% vs bulan lalu</span></div>
              <div className="kpi"><small>Total OPEX</small><b>{fmtRp(stats?.total_opex||0)}</b><span>Budget 82% terpakai</span></div>
              <div className="kpi"><small>Total CAPEX</small><b>{fmtRp(stats?.total_capex||0)}</b><span>Aset baru</span></div>
              <div className="kpi"><small>Perlu Review</small><b>{stats?.need_review||0} dokumen</b><span>STP {stats?.stp_rate||70}%</span></div>
            </div>
            <div className="grid2">
              <div className="card"><h3>OPEX vs CAPEX vs Revenue</h3>
                {stats && [{label:'Revenue',val:stats.total_revenue,color:'#1FB0BC'},{label:'OPEX',val:stats.total_opex,color:'#5079BD'},{label:'CAPEX',val:stats.total_capex,color:'#F2A541'}].map(x=>(
                  <div key={x.label} style={{margin:'10px 0'}}><div style={{display:'flex',justifyContent:'space-between'}}><span>{x.label}</span><b>{fmtRp(x.val)}</b></div><div className="bar"><div style={{width: Math.min(100, (x.val / Math.max(1, stats.total_revenue+stats.total_opex+stats.total_capex))*100*2)+'%', background:x.color}}></div></div></div>
                ))}
              </div>
              <div className="card"><h3>Spending per Cost Center</h3>
                {stats?.by_cost_center?.map(c=>(
                  <div key={c.cost_center} style={{margin:'10px 0'}}><div style={{display:'flex',justifyContent:'space-between'}}><span>{c.cost_center}</span><b>{fmtRp(c.total)}</b></div><div className="bar"><div style={{width: Math.min(100, c.total/150000000*100)+'%'}}></div></div></div>
                ))}
              </div>
            </div>
            <div className="card"><div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:10}}><h3 style={{margin:0}}>Dokumen Terbaru</h3><div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{canCreateUI && <button className="primary" style={{width:'auto',padding:'10px 14px'}} onClick={()=>setShowCreate(!showCreate)}>➕ {showCreate?'Tutup Form':'Tambah Dokumen Manual'}</button>}{canExportUI && <button className="ghost" style={{padding:'10px 14px'}} onClick={()=>handleExportCsv()}>📥 Export CSV Keseluruhan ({docs.length})</button>}{canExportUI && <button className="ghost" style={{padding:'10px 14px'}} onClick={()=>handleExportCsv('Perlu Review')}>📥 Export CSV — Perlu Review</button>}</div></div>
                {showCreate && (
                  <div style={{marginTop:14, background:'#F2F5F9', padding:14, borderRadius:10}}>
                    <h4 style={{margin:'0 0 8px'}}>➕ Tambah Dokumen Manual — {user.role} bisa Create</h4>
                    <p style={{fontSize:12, color:'#64748B'}}>Finance & CFO (dan Staff/Admin) bisa create manual tanpa OCR. Total dihitung otomatis = Subtotal + PPN - PPh.</p>
                    <div className="grid3">
                      <div><label>Nomor Dokumen *</label><input value={createForm.doc_number} onChange={e=>setCreateForm({...createForm, doc_number:e.target.value})} placeholder="NOTA-2026-201"/></div>
                      <div><label>Tanggal</label><input type="date" value={createForm.tanggal} onChange={e=>setCreateForm({...createForm, tanggal:e.target.value})}/></div>
                      <div><label>Jenis</label><select value={createForm.jenis} onChange={e=>setCreateForm({...createForm, jenis:e.target.value})}><option>Nota Pengeluaran</option><option>Invoice Revenue</option><option>Faktur Pajak</option><option>Kwitansi</option></select></div>
                    </div>
                    <label>Vendor *</label><input value={createForm.vendor} onChange={e=>setCreateForm({...createForm, vendor:e.target.value})} placeholder="PT Contoh Vendor"/>
                    <label>Deskripsi *</label><input value={createForm.deskripsi} onChange={e=>setCreateForm({...createForm, deskripsi:e.target.value})} placeholder="Deskripsi barang / jasa"/>
                    <div className="grid3">
                      <div><label>Subtotal</label><input type="number" value={createForm.subtotal} onChange={e=>setCreateForm({...createForm, subtotal:Number(e.target.value)})}/></div>
                      <div><label>PPN</label><input type="number" value={createForm.ppn} onChange={e=>setCreateForm({...createForm, ppn:Number(e.target.value)})}/></div>
                      <div><label>PPh</label><input type="number" value={createForm.pph} onChange={e=>setCreateForm({...createForm, pph:Number(e.target.value)})}/></div>
                    </div>
                    <div className="grid3">
                      <div><label>Klasifikasi</label><select value={createForm.opex_capex} onChange={e=>setCreateForm({...createForm, opex_capex:e.target.value})}><option>OPEX</option><option>CAPEX</option><option>Revenue</option></select></div>
                      <div><label>CoA</label><input value={createForm.coa} onChange={e=>setCreateForm({...createForm, coa:e.target.value})}/></div>
                      <div><label>Cost Center</label><input value={createForm.cost_center} onChange={e=>setCreateForm({...createForm, cost_center:e.target.value})}/></div>
                    </div>
                    <div style={{display:'flex',gap:10,marginTop:10}}><button className="primary" onClick={handleCreateManual} style={{flex:1}}>✅ Simpan Dokumen Manual (Total: {fmtRp(Number(createForm.subtotal)+Number(createForm.ppn)-Number(createForm.pph))})</button><button className="ghost" onClick={()=>setShowCreate(false)}>Batal</button></div>
                  </div>
                )}
                <div style={{marginTop:10, fontSize:12, color:'#64748B'}}>Hak akses kamu (<b>{user.role}</b>): Create: {canCreateUI?'✅ Ya':'❌ Tidak'} | Delete: {canDeleteUI?'✅ Ya (Finance/CFO/Admin)':'❌ Tidak — hanya Finance/CFO/Admin'} | Export CSV: ✅ Ya | Approve: {canApproveUI?'✅ Ya':'❌ Tidak'}</div>
              <div style={{marginBottom:10}}><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="">Semua</option><option value="Perlu Review">Perlu Review</option><option value="Approved">Approved</option><option value="OPEX">OPEX</option><option value="CAPEX">CAPEX</option></select></div>
              <table><thead><tr><th>No</th><th>Vendor</th><th>Deskripsi</th><th>Klasifikasi</th><th>Total</th><th>OCR</th><th>Dibuat Oleh</th><th>Status</th><th>Aksi</th></tr></thead><tbody>
                {filteredDocs.slice(0,20).map(d=>(
                  <tr key={d.id}><td>{d.doc_number}</td><td>{d.vendor}</td><td>{d.deskripsi}</td><td><span className={`badge ${d.opex_capex}`}>{d.opex_capex}</span></td><td>{fmtRp(d.total)}</td><td style={{fontSize:11}}>{d.ocr_provider||'-'}</td><td style={{fontSize:11}}>{d.created_by||'-'}</td><td><span className={`badge ${d.status}`}>{d.status}</span></td><td>{canDeleteUI ? <button className="danger" style={{padding:'6px 10px',fontSize:12}} onClick={()=>handleDelete(d.id, d.doc_number)}>🗑️ Hapus</button> : <span style={{fontSize:11,color:'#94A3B8'}}>—</span>}</td></tr>
                ))}
              </tbody></table>
            </div>
          </>
        )}
        {tab==='upload' && (
          <>
            <h2>📤 Upload & OCR Tesseract Production</h2>
            <div className="alert ok"><b>OCR Tesseract Lokal aktif (Offline):</b> Semua foto diproses di dalam server, tanpa cloud. Pipeline: Preprocessing OpenCV → Tesseract (ind+eng) → Parser Indonesia. Cek provider harus <code>tesseract-local</code> di hasil upload & di <code>GET /health</code>.</div>
            <div className="card">
              <h3>1. Upload Foto / PDF Nota Beneran</h3>
              <input ref={fileRef} type="file" accept="image/*,.pdf" onChange={handleFileUpload} style={{display:'none'}}/>
              <button className="primary" onClick={()=>fileRef.current?.click()} disabled={loading}>{loading?'⏳ OCR sedang membaca...':'📸 Pilih Foto / PDF Nota — Upload & OCR Tesseract'}</button>
              <p style={{fontSize:13, color:'#64748B'}}>Tips foto: tegak, terang, semua angka terlihat, jangan terpotong. Format: JPG / PNG / PDF, maks 20 MB.</p>
              {uploadInfo && (
                <div className="alert ok"><b>Provider:</b> {uploadInfo.ocr_provider} | <b>OCR Confidence:</b> {(uploadInfo.ocr_confidence*100).toFixed(1)}% | <b>File:</b> {uploadInfo.file_name} ({uploadInfo.size} bytes)<br/><b>Raw OCR (cuplikan):</b> <span style={{fontSize:12}}>{uploadInfo.extracted?.raw_text?.slice(0,300)||'-'}</span></div>
              )}
            </div>
            <div className="grid2">
              <div className="card"><h3>2. Koreksi Hasil OCR (Human-in-the-Loop)</h3>
                <label>Vendor / Pelanggan</label><input value={form.vendor} onChange={e=>setForm({...form, vendor:e.target.value})}/>
                <label>Deskripsi Barang / Jasa</label><textarea rows={3} value={form.deskripsi} onChange={e=>setForm({...form, deskripsi:e.target.value})}/>
                <label>Nomor Dokumen</label><input value={form.doc_number} onChange={e=>setForm({...form, doc_number:e.target.value})}/>
                <div className="grid3">
                  <div><label>Subtotal (Rp)</label><input type="number" value={form.subtotal} onChange={e=>setForm({...form, subtotal:Number(e.target.value)})}/></div>
                  <div><label>PPN (Rp)</label><input type="number" value={form.ppn} onChange={e=>setForm({...form, ppn:Number(e.target.value)})}/></div>
                  <div><label>PPh (Rp)</label><input type="number" value={form.pph} onChange={e=>setForm({...form, pph:Number(e.target.value)})}/></div>
                </div>
                <label>Threshold CAPEX (Rp)</label><input type="number" value={form.threshold} onChange={e=>setForm({...form, threshold:Number(e.target.value)})}/>
                <button className="primary" onClick={process} disabled={loading}>{loading?'⏳ Memproses...':'🤖 Proses Klasifikasi (Tanpa Upload)'}</button>
              </div>
              <div className="card"><h3>3. Hasil AI</h3>
                {!result && <p>Belum ada hasil. Upload foto nota atau klik Proses Klasifikasi.</p>}
                {result && (
                  <>
                    <div style={{display:'flex',gap:10}}><div className="kpi" style={{flex:1}}><small>Prediksi</small><b>{result.predicted}</b><span>Confidence {(result.confidence*100).toFixed(1)}%</span></div><div className="kpi" style={{flex:1}}><small>CoA</small><b style={{fontSize:15}}>{result.coa}</b></div><div className="kpi" style={{flex:1}}><small>Total</small><b>{fmtRp(result.total)}</b></div></div>
                    <div className="alert ok"><b>Alasan AI:</b> {result.reason}</div>
                    <h4>Validasi Otomatis</h4>
                    {result.validations.map((v,i)=>(
                      <div key={i} className={`alert ${v.status==='ok'?'ok':v.status==='warn'?'warn':'fail'}`}>{v.status==='ok'?'✅':v.status==='warn'?'⚠️':'❌'} <b>{v.name}:</b> {v.message}</div>
                    ))}
                    <div style={{display:'flex',gap:10, marginTop:12}}>
                      <button className="primary" onClick={saveDoc} style={{flex:1}}>✅ Simpan & Posting ke ERP</button>
                      <button className="ghost" onClick={()=>setResult({...result, predicted: result.predicted==='CAPEX'?'OPEX':'CAPEX'})}>✏️ Koreksi (Flip)</button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </>
        )}
        {tab==='approval' && (
          <>
            <h2>✅ Validasi & Approval</h2>
            <p style={{fontSize:13}}>Login sebagai <b>{user.role}</b> — {user.role==='STAFF' ? 'Staff tidak dapat approve, hanya bisa upload & ajukan.' : user.role==='FINANCE' ? 'Finance dapat approve sampai Rp 50 jt. Di atas itu harus CFO.' : 'CFO dapat approve semua nilai.'}</p>
            <div className="card"><table><thead><tr><th>No</th><th>Vendor</th><th>Deskripsi</th><th>Klasifikasi</th><th>Total</th><th>Status</th><th>Aksi</th></tr></thead><tbody>
              {docs.filter(d=>['Perlu Review','Menunggu Approval'].includes(d.status)).map(d=>(
                <tr key={d.id}><td>{d.doc_number}</td><td>{d.vendor}</td><td>{d.deskripsi}</td><td><span className={`badge ${d.opex_capex}`}>{d.opex_capex}</span></td><td>{fmtRp(d.total)}</td><td>{d.status}</td><td>{canApproveUI ? <button className="success" onClick={()=>approve(d.id)}>Approve</button> : <span style={{fontSize:12, color:'#64748B'}}>Hanya Finance / CFO</span>}</td></tr>
              ))}
            </tbody></table>
            {docs.filter(d=>['Perlu Review','Menunggu Approval'].includes(d.status)).length===0 && <p>🎉 Tidak ada yang perlu review. Semua STP!</p>}
            {canApproveUI && <><div style={{marginTop:16}}><label>Alasan Tolak (wajib jika tolak)</label><input value={rejectReason} onChange={e=>setRejectReason(e.target.value)} placeholder="Contoh: Nominal tidak sesuai PO..."/></div>
            <div style={{marginTop:10}}>{docs.filter(d=>['Perlu Review','Menunggu Approval'].includes(d.status)).map(d=>(
              <div key={d.id} style={{display:'flex',gap:10, alignItems:'center', margin:'6px 0'}}><span>{d.doc_number} — {d.vendor}</span><button className="danger" onClick={()=>reject(d.id)}>Tolak</button></div>
            ))}</div></>}
            </div>
          </>
        )}
        {tab==='report' && (
          <>
            <h2>📈 Laporan OPEX / CAPEX</h2><div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:10}}><button className="ghost" onClick={()=>handleExportCsv()}>📥 Export CSV Keseluruhan</button><button className="ghost" onClick={()=>handleExportCsv('Approved')}>📥 Export CSV — Approved</button><button className="ghost" onClick={()=>handleExportCsv('CAPEX')}>📥 Export CSV — CAPEX (via filter di backend? gunakan q)</button></div><p style={{fontSize:12,color:'#64748B'}}>Export CSV mengunduh semua kolom (id, nomor, vendor, subtotal, PPN, PPh, total, OPEX/CAPEX, CoA, cost center, status, created_by, approved_by, dll) — bisa dibuka di Excel / Google Sheets.</p>
            <div className="grid2">
              <div className="card"><h3>OPEX per CoA</h3>{stats?.opex_by_coa?.map(x=>(<div key={x.coa} style={{display:'flex',justifyContent:'space-between', margin:'8px 0'}}><span>{x.coa}</span><b>{fmtRp(x.total)}</b></div>))}</div>
              <div className="card"><h3>CAPEX per CoA</h3>{stats?.capex_by_coa?.map(x=>(<div key={x.coa} style={{display:'flex',justifyContent:'space-between', margin:'8px 0'}}><span>{x.coa}</span><b>{fmtRp(x.total)}</b></div>))}</div>
            </div>
            <div className="card"><h3>Jadwal Depresiasi CAPEX (Straight Line 48 Bulan)</h3>
              <table><thead><tr><th>Aset</th><th>No Dokumen</th><th>Nilai CAPEX</th><th>Depresiasi / Bulan</th><th>Mulai</th></tr></thead><tbody>
                {report?.capex_depreciation?.map((r,i)=>(<tr key={i}><td>{r.aset}</td><td>{r.doc_number}</td><td>{fmtRp(r.nilai)}</td><td>{fmtRp(r.per_bulan)}</td><td>{r.mulai}</td></tr>))}
              </tbody></table>
            </div>
          </>
        )}
        {tab==='users' && (
  <>
    {user?.role !== 'CFO' ? (
      <div className="card"><h2>🔒 Kelola Akun — Hanya CFO</h2><p>Maaf, <b>{user?.role}</b> tidak bisa create akun & edit privilege.</p><p>Hanya role <b>CFO</b> yang bisa create akun, edit privilege, dan hapus akun. Staff & Finance akan ditolak <code>403</code> jika mencoba via API.</p><p>Silakan minta CFO untuk membuatkan / mengubah akun.</p></div>
    ) : (
      <>
        <h2>👥 Kelola Akun — Hanya CFO</h2>
        <p style={{fontSize:13}}>Login sebagai <b>{user.name} (CFO)</b> — kamu satu-satunya role yang bisa create akun & edit privilege pengguna lain.</p>
        <div className="grid2">
          <div className="card"><h3>➕ Tambah Akun Baru</h3>
            <label>Nama Lengkap *</label><input value={userForm.name} onChange={e=>setUserForm({...userForm, name:e.target.value})} placeholder="Contoh: Dina Staff Baru"/>
            <label>Email *</label><input value={userForm.email} onChange={e=>setUserForm({...userForm, email:e.target.value})} placeholder="nama@perusahaan.id"/>
            <label>Password * (min 6 karakter)</label><input type="password" value={userForm.password} onChange={e=>setUserForm({...userForm, password:e.target.value})} placeholder="••••••"/>
            <div className="grid3">
              <div><label>Role / Privilege *</label><select value={userForm.role} onChange={e=>setUserForm({...userForm, role:e.target.value})}><option value="STAFF">STAFF — Upload saja</option><option value="FINANCE">FINANCE — Approve ≤ Rp 50 jt</option><option value="CFO">CFO — Approve semua + Kelola Akun</option><option value="ADMIN">ADMIN — Approve semua</option></select></div>
              <div><label>Cost Center</label><input value={userForm.cost_center} onChange={e=>setUserForm({...userForm, cost_center:e.target.value})}/></div>
            </div>
            <div style={{background:'#FEF3C7', padding:10, borderRadius:8, fontSize:12, marginTop:8}}><b>Privilege per Role:</b><br/>• <b>STAFF</b> — Upload & ajukan, tidak bisa approve / delete dokumen / create akun<br/>• <b>FINANCE</b> — Create dokumen, delete dokumen, approve ≤ Rp 50 jt, <b>tidak bisa create akun</b><br/>• <b>CFO</b> — Semua + <b>create akun & edit privilege</b><br/>• <b>ADMIN</b> — Approve semua, tapi <b>tidak bisa create akun</b> (hanya CFO)</div>
            <button className="primary" onClick={createUser} style={{marginTop:10}}>✅ Buat Akun Baru</button>
          </div>
          <div className="card"><h3>ℹ️ Aturan Kelola Akun</h3><ul style={{fontSize:13}}><li>Hanya <b>CFO</b> yang bisa create akun, edit role, nonaktifkan, & hapus akun.</li><li>Staff & Finance yang coba create via API akan ditolak <code>403</code>.</li><li>CFO tidak bisa hapus / demote / nonaktifkan dirinya sendiri.</li><li>Sistem menjaga minimal 1 CFO aktif — CFO terakhir tidak bisa di-demote / dinonaktifkan / dihapus.</li><li>Edit privilege langsung berlaku — user yang diubah harus login ulang untuk token baru (role di token lama masih lama sampai expired).</li><li>Reset password: edit pengguna → isi Password Baru → Simpan.</li></ul><button className="ghost" onClick={loadUsers}>🔄 Refresh Daftar Pengguna</button></div>
        </div>
        <div className="card"><h3>Daftar Pengguna ({usersList.length})</h3>
          <table><thead><tr><th>Nama</th><th>Email</th><th>Role / Privilege</th><th>Cost Center</th><th>Status</th><th>Aksi</th></tr></thead><tbody>
            {usersList.map(u=>(
              editingUserId===u.id ? (
                <tr key={u.id} style={{background:'#FEF3C7'}}><td><input value={editingUser.name} onChange={e=>setEditingUser({...editingUser, name:e.target.value})}/></td><td><input value={editingUser.email} onChange={e=>setEditingUser({...editingUser, email:e.target.value})}/></td><td><select value={editingUser.role} onChange={e=>setEditingUser({...editingUser, role:e.target.value})}><option value="STAFF">STAFF</option><option value="FINANCE">FINANCE</option><option value="CFO">CFO</option><option value="ADMIN">ADMIN</option></select><br/><input type="password" value={editingUser.password} onChange={e=>setEditingUser({...editingUser, password:e.target.value})} placeholder="Password baru (kosongkan jika tidak diubah)" style={{marginTop:6}}/></td><td><input value={editingUser.cost_center} onChange={e=>setEditingUser({...editingUser, cost_center:e.target.value})}/></td><td><select value={editingUser.is_active?'true':'false'} onChange={e=>setEditingUser({...editingUser, is_active:e.target.value==='true'})}><option value="true">Aktif</option><option value="false">Nonaktif</option></select></td><td><div style={{display:'flex',gap:6,flexDirection:'column'}}><button className="success" onClick={()=>saveEditUser(u.id)}>💾 Simpan</button><button className="ghost" onClick={()=>setEditingUserId(null)}>Batal</button></div></td></tr>
              ) : (
                <tr key={u.id}><td><b>{u.name}</b>{u.id===user.id && <span style={{fontSize:11, color:'#5079BD'}}> (Kamu)</span>}</td><td>{u.email}</td><td><span className="badge">{u.role}</span><br/><span style={{fontSize:11,color:'#64748B'}}>{u.role==='STAFF'?'Upload saja':u.role==='FINANCE'?'Approve ≤ Rp 50 jt':u.role==='CFO'?'Approve semua + Kelola Akun':'Approve semua'}</span></td><td>{u.cost_center}</td><td><span className={`badge ${u.is_active?'Approved':'Ditolak'}`}>{u.is_active?'✅ Aktif':'⛔ Nonaktif'}</span></td><td><div style={{display:'flex',gap:6,flexWrap:'wrap'}}><button className="ghost" style={{fontSize:12}} onClick={()=>startEditUser(u)}>✏️ Edit Privilege</button><button className="ghost" style={{fontSize:12}} onClick={()=>toggleUserActive(u)}>{u.is_active?'⛔ Nonaktifkan':'✅ Aktifkan'}</button>{u.id!==user.id && <button className="danger" style={{fontSize:12}} onClick={()=>deleteUser(u)}>🗑️ Hapus</button>}</div></td></tr>
              )
            ))}
          </tbody></table>
          {usersList.length===0 && <p>Belum ada pengguna. Klik Refresh atau login sebagai CFO.</p>}
        </div>
      </>
    )}
  </>
)}
{tab==='api' && (
          <>
            <h2>❓ Bantuan</h2>
            <div className="card"><h3>Status Koneksi & OCR</h3><p>API Base: <b>{getApiBase()}</b></p><p>Backend: <b>{conn}</b> | User: <b>{user.name} ({user.role})</b></p><p>Cek manual:</p><p>Hubungi CFO / Admin untuk pembuatan akun, reset password, atau akses.</p>
              
              <h3 style={{marginTop:16}}>Bantuan</h3><ul><li>POST /api/auth/login — Login JWT</li><li>GET /api/auth/me — Profil user</li><li>POST /api/documents/upload-ocr — Upload foto/PDF → OCR Real (Azure/Tesseract)</li><li>POST /api/auth/users — Create Akun (HANYA CFO, Staff/Finance 403)</li><li>PATCH /api/auth/users/{`{id}`} — Edit Privilege (HANYA CFO)</li><li>DELETE /api/auth/users/{`{id}`} — Hapus Akun (HANYA CFO)</li><li>GET /api/auth/users — Daftar Pengguna (HANYA CFO)</li><li>POST /api/documents — Create Manual (Staff/Finance/CFO/Admin)</li><li>DELETE /api/documents/{`{id}`} — Delete (hanya Finance/CFO/Admin)</li><li>GET /api/documents/export/csv — Export CSV Keseluruhan (semua role login, bisa filter ?status= / ?opex_capex= / ?q=)</li><li>POST /api/documents/{`{id}`}/approve — Role Finance/CFO/Admin + cek limit Rp 50 jt</li></ul>
              <h3>Setup Tesseract Lokal (Tidak Perlu API Key)</h3><ol><li>Tidak perlu setup cloud. Tesseract sudah terinstall di Dockerfile.</li><li><code>docker compose down && docker compose up --build</code></li><li>Upload foto nota → cek Provider harus <code>tesseract-local</code></li><li>Tips foto: tegak, terang, angka tidak terpotong, jarak 30-40 cm.</li></ol>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
