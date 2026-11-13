import { FormEvent, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../ui/Icon'
import { useAuth } from '../../lib/api'
import { useRealtime } from '../../providers/RealtimeProvider'
import NotificationDropdown from '../../features/notifications/NotificationDropdown'

export default function MainLayout() {
  const { loggedIn, logout } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [sp] = useSearchParams()
  const [q, setQ] = useState(sp.get('keyword') ?? '')
  const { messageUnread } = useRealtime()

  useEffect(() => { if (loc.pathname === '/' || loc.pathname === '/index.html') setQ(sp.get('keyword') ?? '') }, [loc.pathname, sp])
  useEffect(() => { window.scrollTo(0, 0) }, [loc.pathname])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    nav(q.trim() ? `/?keyword=${encodeURIComponent(q.trim())}#products` : '/')
  }

  return (
    <>
      <header className="site-header">
        <div className="header-inner">
          <Link to="/" className="brand" aria-label="chợmình – trang chủ">
            <span className="brand-mark"><Icon name="bag" size={22} strokeWidth={2} /></span>
            <span className="brand-text">
              <span className="brand-name">chợ<em>mình</em></span>
              <span className="brand-sub">Chợ của sinh viên</span>
            </span>
          </Link>

          <form className="header-search" onSubmit={submit} role="search">
            <Icon name="search" size={18} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm sách, đồ điện tử, đồ xinh..." aria-label="Tìm kiếm" />
            <button type="submit">Tìm kiếm</button>
          </form>

          <nav className="header-nav" aria-label="Chính">
            <NavLink to="/favorites"><Icon name="heart" size={20} /> Yêu thích</NavLink>
            <NavLink to="/messages" aria-label={`Tin nhắn${messageUnread ? `, ${messageUnread} chưa đọc` : ''}`}>
              <Icon name="chat" size={20} /> Tin nhắn
              {messageUnread > 0 && <span className="nav-badge">{messageUnread > 99 ? '99+' : messageUnread}</span>}
            </NavLink>
            {loggedIn && <NotificationDropdown />}
            <NavLink to="/profile" className="nav-account">
              <Icon name="user" size={20} /> Tài khoản
            </NavLink>
            {loggedIn ? (
              <button className="nav-icon" onClick={() => { logout(); nav('/') }} aria-label="Đăng xuất" title="Đăng xuất"><Icon name="logout" size={22} /></button>
            ) : (
              <Link to="/login" className="nav-icon" aria-label="Đăng nhập" title="Đăng nhập"><Icon name="login" size={22} /></Link>
            )}
            <Link to="/post" className="btn-post"><Icon name="boxplus" size={19} /> Đăng tin</Link>
          </nav>
        </div>
      </header>

      <main><Outlet /></main>

      <footer className="site-footer">
        <div className="footer-inner">
          <div>
            <div className="brand-name">chợ<em>mình</em></div>
            <p>Chợ mua bán đồ dùng dành riêng cho sinh viên. Tiết kiệm một chút, sống xanh thêm nhiều.</p>
          </div>
          <div className="footer-links">
            <Link to="/">Trang chủ</Link>
            <Link to="/post">Đăng tin</Link>
            <Link to="/my-products">Tin của tôi</Link>
            <Link to="/messages">Tin nhắn</Link>
          </div>
        </div>
        <div className="footer-copy">© {new Date().getFullYear()} chợmình – Market for Students</div>
      </footer>
    </>
  )
}
