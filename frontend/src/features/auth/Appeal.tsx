import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { API, errText, mediaUrl, toast } from '../../lib/api'

interface MyAppealStatus {
  request_id: number
  status: string
  submit_at: string
  note?: string | null
  message: string
}

export default function Appeal() {
  const nav = useNavigate()
  const appealToken = sessionStorage.getItem('cm_appeal_token') || localStorage.getItem('cm_token') || ''
  const [existing, setExisting] = useState<MyAppealStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [phone, setPhone] = useState('')
  const [otherPhone, setOtherPhone] = useState('')
  const [cccdFront, setCccdFront] = useState('')
  const [cccdBack, setCccdBack] = useState('')
  const [simImg, setSimImg] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState<string | null>(null)
  const [err, setErr] = useState('')

  const fetchAppealStatus = async () => {
    if (!appealToken) {
      setLoading(false)
      return
    }
    try {
      const res = await fetch(`${API}/identity-verification/my-appeal`, {
        headers: { Authorization: `Bearer ${appealToken}` },
      })
      if (res.ok) {
        const data = await res.json()
        setExisting(data)
      }
    } catch {
      /* Bỏ qua nếu chưa nộp đơn nào */
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAppealStatus()
  }, [])

  const uploadDoc = async (file: File, type: 'front' | 'back' | 'sim') => {
    setUploading(type)
    setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API}/upload/image`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${appealToken}` },
        body: fd,
      })
      if (!res.ok) throw new Error('Tải ảnh thất bại')
      const data = await res.json()
      const url = data.image_url || data.detail_url || data.raw_url
      if (type === 'front') setCccdFront(url)
      if (type === 'back') setCccdBack(url)
      if (type === 'sim') setSimImg(url)
      toast('Tải ảnh lên thành công')
    } catch (e) {
      setErr(errText(e))
    } finally {
      setUploading(null)
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!cccdFront || !cccdBack || !simImg) {
      return setErr('Vui lòng tải đủ 3 hình ảnh: Mặt trước CCCD, Mặt sau CCCD và Tin nhắn xác minh SIM chính chủ.')
    }
    setBusy(true)
    setErr('')
    try {
      const res = await fetch(`${API}/identity-verification/appeal`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${appealToken}`,
        },
        body: JSON.stringify({
          contact_phone: phone.trim(),
          other_phone: otherPhone.trim() || null,
          cccd_front_url: cccdFront,
          cccd_back_url: cccdBack,
          sim_ownership_url: simImg,
          note: note.trim() || null,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail?.message || data?.detail || 'Gửi kháng cáo thất bại')
      }
      toast('Đã nộp hồ sơ kháng cáo thành công!')
      fetchAppealStatus()
    } catch (e2) {
      setErr(errText(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card" style={{ maxWidth: 640 }}>
        <Link to="/login" className="auth-back">
          <Icon name="back" size={16} /> Quay lại Đăng nhập
        </Link>
        <h1>Kháng cáo Mở khóa Tài khoản</h1>
        <p className="auth-sub">
          Quy trình thẩm định CCCD và SIM chính chủ (SRS Sequence 6) nhằm xác minh danh tính và mở lại quyền truy cập cho bạn.
        </p>

        {loading ? (
          <div className="loading">Đang kiểm tra hồ sơ...</div>
        ) : !appealToken ? (
          <div className="empty-box">
            <strong>Không tìm thấy phiên kháng cáo</strong>
            <p>Vui lòng đăng nhập bằng tài khoản bị khóa để hệ thống cấp mã xác thực kháng cáo.</p>
            <Link to="/login" className="btn btn-primary" style={{ marginTop: 12 }}>
              Về trang đăng nhập
            </Link>
          </div>
        ) : existing && existing.status === 'PENDING' ? (
          <div className="card" style={{ border: '1px solid var(--border)', padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#e67e22', marginBottom: 12 }}>
              <Icon name="shield" size={24} />
              <strong style={{ fontSize: '1.1rem' }}>Hồ sơ đang chờ phê duyệt</strong>
            </div>
            <p>{existing.message}</p>
            <div className="hint" style={{ marginTop: 8 }}>
              Ngày gửi: {new Date(existing.submit_at).toLocaleString('vi-VN')}
            </div>
            {existing.note && <div style={{ marginTop: 8 }}>Lời giải trình: <i>{existing.note}</i></div>}
            <div style={{ marginTop: 16 }}>
              <button className="btn btn-ghost btn-sm" onClick={fetchAppealStatus}>
                Làm mới trạng thái
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit}>
            {err && <div className="form-error" role="alert">{err}</div>}
            {existing && (
              <div className="hint" style={{ marginBottom: 12, color: 'var(--muted)' }}>
                Tình trạng hồ sơ trước: <b>{existing.status}</b> ({existing.message})
              </div>
            )}

            <div className="row">
              <div className="field">
                <label htmlFor="ap-phone">Số điện thoại chính chủ (*)</label>
                <input
                  id="ap-phone"
                  className="input"
                  type="tel"
                  required
                  placeholder="0912345678"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="ap-other-phone">Số điện thoại phụ / người thân</label>
                <input
                  id="ap-other-phone"
                  className="input"
                  type="tel"
                  placeholder="Không bắt buộc"
                  value={otherPhone}
                  onChange={(e) => setOtherPhone(e.target.value)}
                />
              </div>
            </div>

            <div className="field">
              <span className="label">Ảnh giấy tờ xác thực (*)</span>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginTop: 8 }}>
                <div style={{ border: '1px dashed var(--border)', padding: 12, borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>Mặt trước CCCD</div>
                  {cccdFront ? (
                    <img src={mediaUrl(cccdFront)} alt="Mặt trước" style={{ width: '100%', height: 100, objectFit: 'cover', borderRadius: 4 }} />
                  ) : (
                    <label className="btn btn-ghost btn-sm" style={{ width: '100%' }}>
                      {uploading === 'front' ? 'Đang tải...' : 'Chọn ảnh'}
                      <input type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && uploadDoc(e.target.files[0], 'front')} />
                    </label>
                  )}
                </div>

                <div style={{ border: '1px dashed var(--border)', padding: 12, borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>Mặt sau CCCD</div>
                  {cccdBack ? (
                    <img src={mediaUrl(cccdBack)} alt="Mặt sau" style={{ width: '100%', height: 100, objectFit: 'cover', borderRadius: 4 }} />
                  ) : (
                    <label className="btn btn-ghost btn-sm" style={{ width: '100%' }}>
                      {uploading === 'back' ? 'Đang tải...' : 'Chọn ảnh'}
                      <input type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && uploadDoc(e.target.files[0], 'back')} />
                    </label>
                  )}
                </div>

                <div style={{ border: '1px dashed var(--border)', padding: 12, borderRadius: 8, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>Tra cứu SIM 1414</div>
                  {simImg ? (
                    <img src={mediaUrl(simImg)} alt="SIM chính chủ" style={{ width: '100%', height: 100, objectFit: 'cover', borderRadius: 4 }} />
                  ) : (
                    <label className="btn btn-ghost btn-sm" style={{ width: '100%' }}>
                      {uploading === 'sim' ? 'Đang tải...' : 'Chọn ảnh'}
                      <input type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && uploadDoc(e.target.files[0], 'sim')} />
                    </label>
                  )}
                </div>
              </div>
              <span className="hint">Chụp ảnh rõ nét, không lóa sáng, ảnh SIM thể hiện đúng họ tên và CCCD của bạn.</span>
            </div>

            <div className="field">
              <label htmlFor="ap-note">Lời giải trình / Cam kết</label>
              <textarea
                id="ap-note"
                className="textarea"
                rows={3}
                maxLength={500}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Giải trình lý do vi phạm hoặc cam kết không tái phạm quy chế chợ..."
              />
            </div>

            <button className="btn btn-primary btn-block" disabled={busy || !!uploading}>
              {busy ? 'Đang gửi hồ sơ...' : 'Nộp hồ sơ kháng cáo'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
