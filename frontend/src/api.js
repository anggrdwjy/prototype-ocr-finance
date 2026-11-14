const ENV_API = (import.meta.env.VITE_API_URL || '').trim()
const API = ENV_API === '' ? '' : ENV_API.replace(/\/$/, '')
export function getApiBase(){ return API === '' ? 'relative /api via Nginx (localhost:3000)' : API }
export function getToken(){ return localStorage.getItem('ocr_token') }
export function getUser(){ try{ return JSON.parse(localStorage.getItem('ocr_user')||'null') }catch{ return null } }
export function logout(){ localStorage.removeItem('ocr_token'); localStorage.removeItem('ocr_user'); window.location.reload() }
export async function api(path, opts={}) {
  const url = `${API}${path}`
  const token = getToken()
  const headers = { ...(opts.isForm ? {} : {'Content-Type':'application/json'}), ...(token ? {Authorization: `Bearer ${token}`} : {}), ...(opts.headers||{}) }
  let res
  try {
    res = await fetch(url, { ...opts, headers })
  } catch (e) {
    throw new Error(`Gagal fetch ke ${url}. Cek: 1) docker ps (backend jalan?) 2) curl http://localhost:8000/health 3) curl http://localhost:3000/api/documents — Detail: ${e.message}`)
  }
  if (res.status === 401) {
    // Token kadaluarsa -> logout otomatis
    localStorage.removeItem('ocr_token'); localStorage.removeItem('ocr_user')
    window.location.reload()
    throw new Error('Sesi habis, silakan login ulang.')
  }
  if (!res.ok) {
    const err = await res.json().catch(()=>({detail:'Error '+res.status}))
    throw new Error(err.detail || ('HTTP '+res.status))
  }
  return res.json()
}
export async function apiUpload(path, formData){
  const token = getToken()
  const res = await fetch(`${API}${path}`, { method:'POST', headers: token ? {Authorization: `Bearer ${token}`} : {}, body: formData })
  if (res.status===401){ localStorage.removeItem('ocr_token'); localStorage.removeItem('ocr_user'); window.location.reload(); throw new Error('Sesi habis') }
  if (!res.ok){ const err = await res.json().catch(()=>({detail:'Error '+res.status})); throw new Error(err.detail||('HTTP '+res.status)) }
  return res.json()
}
export const fmtRp = (n) => 'Rp ' + Number(n||0).toLocaleString('id-ID')

export async function apiExportCsv(path, filename){
  const token = getToken()
  const res = await fetch(`${API}${path}`, { headers: token ? {Authorization: `Bearer ${token}`} : {} })
  if (res.status===401){ localStorage.removeItem('ocr_token'); localStorage.removeItem('ocr_user'); window.location.reload(); throw new Error('Sesi habis') }
  if (!res.ok){ const err = await res.json().catch(()=>({detail:'Error '+res.status})); throw new Error(err.detail||('HTTP '+res.status)) }
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  // Ambil filename dari header jika ada
  const cd = res.headers.get('Content-Disposition') || ''
  let fname = filename
  const m = cd.match(/filename=([^;]+)/)
  if (m) fname = m[1].replace(/["']/g,'').trim()
  a.download = fname
  document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url)
  return fname
}
