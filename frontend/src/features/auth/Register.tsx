import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, ApiError, setToken, toast } from '../../lib/api'

export default function Register() {
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    if (pw.length < 6) return setErr('Mật khẩu cần tối thiểu 6 ký tự.')
    if (pw !== pw2) return setErr('Mật khẩu nhập lại không khớp.')
    setBusy(true)
    try {
      // account_type mặc định "Ca Nhan"; sẽ tự chuyển "Sinh Vien" sau khi xác minh email .edu.vn
      await api.post('/auth/register', { Email: email.trim(), PassWord: pw, account_type: 'Ca Nhan' })
      const r = await api.login(email.trim(), pw)
      setToken(r.access_token)
      toast('Tạo tài khoản thành công! Xác minh sinh viên để tăng độ tin cậy nhé.')
      nav('/profile?tab=student', { replace: true })
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 409) setErr('Email này đã được đăng ký.')
      else setErr(e2 instanceof Error ? e2.message : 'Đăng ký thất bại')
    } finally { setBusy(false) }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <Link to="/" className="brand">
          <span className="brand-mark"><Icon name="bag" size={22} strokeWidth={2} /></span>
          <span className="brand-text"><span className="brand-name">chợ<em>mình</em></span><span className="brand-sub">Chợ của sinh viên</span></span>
        </Link>
        <h1>Tạo tài khoản</h1>
        <p className="auth-sub">Vài giây thôi là bạn có thể đăng bán món đồ đầu tiên.</p>
        {err && <div className="form-error" role="alert">{err}</div>}
        <form onSubmit={submit}>
          <div className="field"><label htmlFor="r-email">Email</label><input id="r-email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="ban@email.com" /></div>
          <div className="field"><label htmlFor="r-pw">Mật khẩu</label><input id="r-pw" className="input" type="password" required minLength={6} value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" /><span className="hint">Tối thiểu 6 ký tự</span></div>
          <div className="field"><label htmlFor="r-pw2">Nhập lại mật khẩu</label><input id="r-pw2" className="input" type="password" required value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" /></div>
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Đang tạo...' : 'Đăng ký'}</button>
        </form>
        <p className="auth-switch">Đã có tài khoản? <Link to="/login">Đăng nhập</Link></p>
      </div>
    </div>
  )
}
