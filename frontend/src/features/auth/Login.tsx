import { FormEvent, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, ApiError, getUserAccountType, getUserRole, setToken, toast } from '../../lib/api'
import GoogleLoginButton from './GoogleLoginButton'

function Brand() {
  return (
    <Link to="/" className="brand">
      <span className="brand-mark"><Icon name="bag" size={22} strokeWidth={2} /></span>
      <span className="brand-text"><span className="brand-name">chợ<em>mình</em></span><span className="brand-sub">Chợ của sinh viên</span></span>
    </Link>
  )
}

/** Quên mật khẩu 3 bước: email → OTP → mật khẩu mới (khớp /auth/forgot-password/*). */
function ForgotPassword({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const run = async (fn: () => Promise<void>) => {
    setErr(''); setBusy(true)
    try { await fn() } catch (e) { setErr(e instanceof Error ? e.message : 'Có lỗi xảy ra') } finally { setBusy(false) }
  }

  const s1 = (e: FormEvent) => { e.preventDefault(); run(async () => { await api.post('/auth/forgot-password/request-otp', { email }); setStep(2) }) }
  const s2 = (e: FormEvent) => { e.preventDefault(); run(async () => { const r = await api.post<{ reset_token: string }>('/auth/forgot-password/verify-otp', { email, otp_code: otp }); setResetToken(r.reset_token); setStep(3) }) }
  const s3 = (e: FormEvent) => {
    e.preventDefault()
    run(async () => {
      await api.post('/auth/forgot-password/reset', { reset_token: resetToken, new_password: pw, confirm_password: pw2 })
      toast('Đã đặt lại mật khẩu, hãy đăng nhập nhé!')
      onBack()
    })
  }

  return (
    <>
      <button className="auth-back" onClick={onBack}><Icon name="back" size={16} /> Quay lại đăng nhập</button>
      <h1>Quên mật khẩu</h1>
      <p className="auth-sub">{step === 1 ? 'Nhập email để nhận mã OTP 6 số.' : step === 2 ? `Mã OTP đã gửi tới ${email}.` : 'Tạo mật khẩu mới (tối thiểu 6 ký tự).'}</p>
      <div className="steps">{[1, 2, 3].map((n) => <span key={n} className={n <= step ? 'on' : ''} />)}</div>
      {err && <div className="form-error" role="alert">{err}</div>}
      {step === 1 && (
        <form onSubmit={s1}>
          <div className="field"><label htmlFor="fp-email">Email</label><input id="fp-email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Đang gửi...' : 'Gửi mã OTP'}</button>
        </form>
      )}
      {step === 2 && (
        <form onSubmit={s2}>
          <div className="field"><label htmlFor="fp-otp">Mã OTP</label><input id="fp-otp" className="input otp-input" inputMode="numeric" maxLength={6} required value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} /></div>
          <button className="btn btn-primary btn-block" disabled={busy || otp.length !== 6}>{busy ? 'Đang kiểm tra...' : 'Xác nhận'}</button>
          <p className="auth-switch"><button type="button" className="link-btn" onClick={() => run(async () => { await api.post('/auth/forgot-password/request-otp', { email }); toast('Đã gửi lại mã OTP') })}>Gửi lại mã</button></p>
        </form>
      )}
      {step === 3 && (
        <form onSubmit={s3}>
          <div className="field"><label htmlFor="fp-pw">Mật khẩu mới</label><input id="fp-pw" className="input" type="password" minLength={6} required value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" /></div>
          <div className="field"><label htmlFor="fp-pw2">Nhập lại mật khẩu</label><input id="fp-pw2" className="input" type="password" minLength={6} required value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" /></div>
          <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Đang lưu...' : 'Đặt lại mật khẩu'}</button>
        </form>
      )}
    </>
  )
}

export default function Login() {
  const nav = useNavigate()
  const [sp] = useSearchParams()
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [forgot, setForgot] = useState(false)
  const [banned, setBanned] = useState(false)

  const redirectAfterLogin = () => {
    const role = getUserRole()
    const accType = getUserAccountType()
    const isAdm = role === 1 || role === 4 || accType === 'Admin' || accType === 'Staff'

    if (isAdm) {
      nav('/admin', { replace: true })
    } else {
      const next = sp.get('next')
      if (next && next.startsWith('/') && !next.startsWith('/admin')) {
        nav(next, { replace: true })
      } else {
        nav('/', { replace: true })
      }
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr(''); setBusy(true); setBanned(false)
    try {
      const r = await api.login(email.trim(), pw)
      setToken(r.access_token)
      redirectAfterLogin()
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 403) {
        const d = (e2.data as any)?.detail
        if (d?.appeal_token) {
          sessionStorage.setItem('cm_appeal_token', d.appeal_token)
          setBanned(true)
        }
        setErr(d?.message ?? 'Tài khoản của bạn đã bị khóa do vi phạm quy chế.')
      } else if (e2 instanceof ApiError && e2.status === 404) {
        setErr('Sai email hoặc mật khẩu.')
      } else setErr(e2 instanceof Error ? e2.message : 'Đăng nhập thất bại')
    } finally { setBusy(false) }
  }

  const onGoogleSuccess = async (idToken: string) => {
    setErr(''); setBusy(true); setBanned(false)
    try {
      const r = await api.loginGoogle(idToken)
      setToken(r.access_token)
      toast('Đăng nhập bằng Google thành công!')
      redirectAfterLogin()
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 403) {
        const d = (e2.data as any)?.detail
        if (d?.appeal_token) {
          sessionStorage.setItem('cm_appeal_token', d.appeal_token)
          setBanned(true)
        }
        setErr(typeof d === 'string' ? d : d?.message ?? 'Tài khoản Google này đã bị khóa hoặc chặn khỏi hệ thống.')
      } else if (e2 instanceof ApiError && e2.status === 401) {
        setErr(e2.message || 'Xác thực tài khoản Google thất bại hoặc phiên đã hết hạn.')
      } else {
        setErr(e2 instanceof Error ? e2.message : 'Đăng nhập bằng Google thất bại.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        {forgot ? <ForgotPassword onBack={() => setForgot(false)} /> : (
          <>
            <Brand />
            <h1>Chào mừng quay lại</h1>
            <p className="auth-sub">Đăng nhập để mua bán, nhắn tin và lưu món yêu thích.</p>
            {err && <div className="form-error" role="alert">{err}</div>}
            {banned && (
              <div style={{ marginBottom: 16 }}>
                <Link to="/appeal" className="btn btn-soft btn-block" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                  <Icon name="shield" size={16} /> Gửi hồ sơ kháng cáo mở khóa
                </Link>
              </div>
            )}
            <form onSubmit={submit}>
              <div className="field"><label htmlFor="l-email">Email</label><input id="l-email" className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="ban@email.com" /></div>
              <div className="field"><label htmlFor="l-pw">Mật khẩu</label><input id="l-pw" className="input" type="password" required value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" /></div>
              <div className="auth-row"><button type="button" className="link-btn" onClick={() => setForgot(true)}>Quên mật khẩu?</button></div>
              <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Đang đăng nhập...' : 'Đăng nhập'}</button>
            </form>

            <div className="auth-divider">
              <span>hoặc tiếp tục với</span>
            </div>

            <GoogleLoginButton
              text="signin_with"
              disabled={busy}
              onSuccess={onGoogleSuccess}
              onError={(msg) => setErr(msg)}
            />

            <p className="auth-switch">Chưa có tài khoản? <Link to="/register">Đăng ký ngay</Link></p>
          </>
        )}
      </div>
    </div>
  )
}
