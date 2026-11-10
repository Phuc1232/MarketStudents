import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, District, errText, mediaUrl, Province, toast, useAuth, Ward } from '../../lib/api'

interface Me { Email: string; account_type: string; isActive: boolean }
interface Prof { first_name?: string | null; last_name?: string | null; phone_number?: string | null; avatar_url?: string | null; bio?: string | null; type_mode?: string | null }
interface Addr { address_id: number; ward_id: number; specific_name: string; type: string; is_default: boolean }

type Tab = 'profile' | 'address' | 'security' | 'student'
const TABS: [Tab, string][] = [['profile', 'Hồ sơ'], ['address', 'Địa chỉ'], ['security', 'Bảo mật'], ['student', 'Sinh viên']]

export default function Profile() {
  const [sp, setSp] = useSearchParams()
  const tab = (TABS.some(([k]) => k === sp.get('tab')) ? sp.get('tab') : 'profile') as Tab
  const nav = useNavigate()
  const { logout } = useAuth()
  const [me, setMe] = useState<Me | null>(null)
  const [prof, setProf] = useState<Prof>({})

  useEffect(() => {
    api.get<Me>('/user/me').then(setMe).catch((e) => toast(errText(e), 'err'))
    api.get<Prof>('/user/profile/me').then(setProf).catch(() => {})
  }, [])

  const name = `${prof.last_name ?? ''} ${prof.first_name ?? ''}`.trim() || me?.Email.split('@')[0] || 'Bạn'

  return (
    <div className="container page">
      <div className="pf-top">
        <span className="pf-avatar">{prof.avatar_url ? <img src={mediaUrl(prof.avatar_url)} alt="" /> : name.slice(0, 1).toUpperCase()}</span>
        <div>
          <h1>{name}</h1>
          <div className="hint">{me?.Email}{me?.account_type === 'Sinh Vien' && <span className="chip chip-soft">Sinh viên đã xác minh</span>}</div>
        </div>
        <div className="pf-links">
          <Link to="/notifications" className="btn btn-ghost btn-sm"><Icon name="bell" size={16} /> Thông báo</Link>
          <Link to="/my-products" className="btn btn-ghost btn-sm"><Icon name="tag" size={16} /> Tin của tôi</Link>
          <button className="btn btn-ghost btn-sm" onClick={() => { logout(); nav('/') }}><Icon name="logout" size={16} /> Đăng xuất</button>
        </div>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setSp({ tab: k })}>{l}</button>)}
      </div>

      <div className="pf-body">
        {tab === 'profile' && <ProfileForm prof={prof} onSaved={setProf} />}
        {tab === 'address' && <Addresses />}
        {tab === 'security' && <Security />}
        {tab === 'student' && <Student verified={me?.account_type === 'Sinh Vien'} onVerified={() => setMe((m) => (m ? { ...m, account_type: 'Sinh Vien' } : m))} />}
      </div>
    </div>
  )
}

function ProfileForm({ prof, onSaved }: { prof: Prof; onSaved: (p: Prof) => void }) {
  const [f, setF] = useState<Prof>(prof)
  const [busy, setBusy] = useState(false)
  useEffect(() => setF(prof), [prof])
  const set = (k: keyof Prof, v: string) => setF((o) => ({ ...o, [k]: v }))

  const pickAvatar = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; e.target.value = ''
    if (!file) return
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await api.upload<{ image_url: string }>('/upload/image', fd)
      set('avatar_url', r.image_url)
    } catch (e2) { toast(errText(e2), 'err') }
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true)
    try {
      const r = await api.put<Prof>('/user/profile/me', { first_name: f.first_name || null, last_name: f.last_name || null, phone_number: f.phone_number || null, avatar_url: f.avatar_url || null, bio: f.bio || null, type_mode: f.type_mode || 'light' })
      onSaved(r); toast('Đã lưu hồ sơ')
    } catch (e2) { toast(errText(e2), 'err') } finally { setBusy(false) }
  }
  return (
    <form className="card" onSubmit={submit}>
      <div className="field">
        <span className="label">Ảnh đại diện</span>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center' }}>
          <span className="pf-avatar" style={{ width: 64, height: 64, fontSize: 24 }}>{f.avatar_url ? <img src={mediaUrl(f.avatar_url)} alt="" /> : <Icon name="user" size={26} />}</span>
          <label className="btn btn-ghost btn-sm">Đổi ảnh<input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={pickAvatar} /></label>
        </div>
      </div>
      <div className="row">
        <div className="field"><label htmlFor="pf-ln">Họ và tên đệm</label><input id="pf-ln" className="input" value={f.last_name ?? ''} onChange={(e) => set('last_name', e.target.value)} maxLength={100} /></div>
        <div className="field"><label htmlFor="pf-fn">Tên</label><input id="pf-fn" className="input" value={f.first_name ?? ''} onChange={(e) => set('first_name', e.target.value)} maxLength={100} /></div>
      </div>
      <div className="field"><label htmlFor="pf-ph">Số điện thoại</label><input id="pf-ph" className="input" inputMode="tel" value={f.phone_number ?? ''} onChange={(e) => set('phone_number', e.target.value)} maxLength={20} /></div>
      <div className="field"><label htmlFor="pf-bio">Giới thiệu</label><textarea id="pf-bio" className="textarea" value={f.bio ?? ''} onChange={(e) => set('bio', e.target.value)} placeholder="Vài dòng về bạn (khoa, trường, món hay bán...)" /></div>
      <button className="btn btn-primary" disabled={busy}>{busy ? 'Đang lưu...' : 'Lưu thay đổi'}</button>
    </form>
  )
}

function Addresses() {
  const [list, setList] = useState<Addr[]>([])
  const [provinces, setProvinces] = useState<Province[]>([])
  const [districts, setDistricts] = useState<District[]>([])
  const [wards, setWards] = useState<Ward[]>([])
  const [f, setF] = useState({ province: '', district: '', ward: '', name: '', type: 'Nhà riêng', def: true })
  const load = () => api.get<Addr[]>('/user/address/me').then(setList).catch(() => {})
  useEffect(() => { load(); api.get<Province[]>('/masterdata/provinces').then(setProvinces).catch(() => {}) }, [])
  useEffect(() => { setDistricts([]); setWards([]); setF((o) => ({ ...o, district: '', ward: '' })); if (f.province) api.get<District[]>(`/masterdata/provinces/${f.province}/districts`).then(setDistricts).catch(() => {}) }, [f.province])
  useEffect(() => { setWards([]); setF((o) => ({ ...o, ward: '' })); if (f.district) api.get<Ward[]>(`/masterdata/districts/${f.district}/ward`).then(setWards).catch(() => {}) }, [f.district])

  const add = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/user/address/me', { ward_id: Number(f.ward), specific_name: f.name.trim(), type: f.type, is_default: f.def })
      toast('Đã thêm địa chỉ'); setF((o) => ({ ...o, name: '' })); load()
    } catch (e2) { toast(errText(e2), 'err') }
  }
  const del = async (id: number) => {
    if (!confirm('Xóa địa chỉ này?')) return
    try { await api.del(`/user/addresses/${id}`); load() } catch (e) { toast(errText(e), 'err') }
  }

  return (
    <div className="card">
      {list.length === 0 ? <p className="hint">Bạn chưa lưu địa chỉ giao dịch nào.</p> : list.map((a) => (
        <div className="addr" key={a.address_id}>
          <Icon name="pin" size={20} />
          <div><b>{a.type}</b> {a.is_default && <span className="chip chip-soft">Mặc định</span>}<div>{a.specific_name}</div></div>
          <button className="btn btn-danger btn-sm" onClick={() => del(a.address_id)} aria-label="Xóa địa chỉ"><Icon name="trash" size={14} /></button>
        </div>
      ))}
      <form className="addr-form" onSubmit={add}>
        <h3>Thêm địa chỉ mới</h3>
        <div className="row row-3">
          <select className="select" required value={f.province} onChange={(e) => setF({ ...f, province: e.target.value })} aria-label="Tỉnh / Thành"><option value="">Tỉnh / Thành</option>{provinces.map((x) => <option key={x.province_id} value={x.province_id}>{x.province_name}</option>)}</select>
          <select className="select" required value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })} disabled={!districts.length} aria-label="Quận / Huyện"><option value="">Quận / Huyện</option>{districts.map((x) => <option key={x.district_id} value={x.district_id}>{x.district_name}</option>)}</select>
          <select className="select" required value={f.ward} onChange={(e) => setF({ ...f, ward: e.target.value })} disabled={!wards.length} aria-label="Phường / Xã"><option value="">Phường / Xã</option>{wards.map((x) => <option key={x.ward_id} value={x.ward_id}>{x.ward_name}</option>)}</select>
        </div>
        <div className="field" style={{ marginTop: 14 }}><input className="input" required maxLength={255} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Số nhà, tên đường, KTX..." aria-label="Địa chỉ cụ thể" /></div>
        <div className="row">
          <div className="field"><select className="select" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })} aria-label="Loại địa chỉ"><option>Nhà riêng</option><option>Ký túc xá</option><option>Công ty</option></select></div>
          <label className="field" style={{ display: 'flex', alignItems: 'center', gap: 8, gridAutoFlow: 'column', justifyContent: 'start' }}><input type="checkbox" checked={f.def} onChange={(e) => setF({ ...f, def: e.target.checked })} /> Đặt làm mặc định</label>
        </div>
        <button className="btn btn-primary">Thêm địa chỉ</button>
      </form>
    </div>
  )
}

function Security() {
  const [cur, setCur] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr('')
    if (pw.length < 6) return setErr('Mật khẩu mới cần tối thiểu 6 ký tự.')
    if (pw !== pw2) return setErr('Mật khẩu nhập lại không khớp.')
    setBusy(true)
    try { await api.put('/user/password/me', { current_password: cur, new_password: pw }); toast('Đã đổi mật khẩu'); setCur(''); setPw(''); setPw2('') }
    catch (e2) { setErr(errText(e2)) } finally { setBusy(false) }
  }
  return (
    <form className="card" onSubmit={submit}>
      {err && <div className="form-error" role="alert">{err}</div>}
      <div className="field"><label htmlFor="sc-c">Mật khẩu hiện tại</label><input id="sc-c" className="input" type="password" required value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" /></div>
      <div className="field"><label htmlFor="sc-n">Mật khẩu mới</label><input id="sc-n" className="input" type="password" required minLength={6} value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" /></div>
      <div className="field"><label htmlFor="sc-n2">Nhập lại mật khẩu mới</label><input id="sc-n2" className="input" type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" /></div>
      <button className="btn btn-primary" disabled={busy}>{busy ? 'Đang lưu...' : 'Đổi mật khẩu'}</button>
    </form>
  )
}

function Student({ verified, onVerified }: { verified: boolean; onVerified: () => void }) {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [otp, setOtp] = useState('')
  const [busy, setBusy] = useState(false)
  const [cardDone, setCardDone] = useState(false)

  if (verified) return <div className="verified"><Icon name="shield" size={24} /> Tài khoản của bạn đã được xác minh là sinh viên.</div>

  const run = async (fn: () => Promise<void>) => { setBusy(true); try { await fn() } catch (e) { toast(errText(e), 'err') } finally { setBusy(false) } }
  const request = (e?: FormEvent) => { e?.preventDefault(); run(async () => { await api.post('/user/verify-student/request-otp', { edu_email: email.trim() }); setSent(true); toast('Đã gửi mã OTP tới email trường') }) }
  const confirmOtp = (e: FormEvent) => { e.preventDefault(); run(async () => { await api.post('/user/verify-student/confirm-otp', { edu_email: email.trim(), otp_code: otp }); toast('Xác minh sinh viên thành công!'); onVerified() }) }
  const uploadCard = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; e.target.value = ''
    if (!file) return
    run(async () => {
      const fd = new FormData(); fd.append('file', file)
      const r = await api.upload<{ doc_key: string }>('/upload/private-document', fd)
      await api.post('/user/verify-student/upload-card', { student_card_img: r.doc_key })
      setCardDone(true); toast('Đã gửi ảnh thẻ sinh viên, vui lòng chờ duyệt')
    })
  }

  return (
    <div className="card">
      <p className="hint" style={{ marginBottom: 16 }}>Xác minh bằng email trường (đuôi .edu.vn) để có huy hiệu “Sinh viên” và tăng độ tin cậy khi mua bán.</p>
      {!sent ? (
        <form onSubmit={request}>
          <div className="field"><label htmlFor="st-e">Email trường</label><input id="st-e" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="mssv@truong.edu.vn" /></div>
          <button className="btn btn-primary" disabled={busy}>{busy ? 'Đang gửi...' : 'Gửi mã OTP'}</button>
        </form>
      ) : (
        <form onSubmit={confirmOtp}>
          <div className="field"><label htmlFor="st-o">Mã OTP gửi tới {email}</label><input id="st-o" className="input otp-input" inputMode="numeric" maxLength={6} required value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} /></div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-primary" disabled={busy || otp.length !== 6}>Xác nhận</button>
            <button type="button" className="btn btn-ghost" onClick={() => request()} disabled={busy}>Gửi lại mã</button>
          </div>
        </form>
      )}
      <div className="or">— hoặc nếu trường không có email —</div>
      {cardDone ? <div className="form-ok">Đã nhận ảnh thẻ sinh viên của bạn, chờ quản trị viên duyệt.</div> : (
        <label className="btn btn-ghost">Tải ảnh thẻ sinh viên<input type="file" accept="image/png,image/jpeg,application/pdf" hidden onChange={uploadCard} /></label>
      )}
    </div>
  )
}
