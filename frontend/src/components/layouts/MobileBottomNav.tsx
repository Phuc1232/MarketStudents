import { Link, useLocation } from 'react-router-dom'
import Icon from '../ui/Icon'
import { useRealtime } from '../../providers/RealtimeProvider'

export default function MobileBottomNav() {
  const { pathname } = useLocation()
  const path = pathname.replace(/\.html$/, '').replace('/index', '/')
  const { messageUnread } = useRealtime()
  const items = [['/', 'bag', 'Trang chủ'], ['/favorites', 'heart', 'Yêu thích'], ['/post', 'boxplus', 'Đăng tin'], ['/messages', 'chat', 'Tin nhắn'], ['/profile', 'user', 'Tài khoản']]
  return <nav className="mobile-bottom-nav" aria-label="Điều hướng điện thoại">
    {items.map(([to, icon, label]) => <Link key={to} to={to} aria-current={path === to ? 'page' : undefined}>
      <span className="mobile-nav-icon"><Icon name={icon} size={22} />{to === '/messages' && messageUnread > 0 && <span className="nav-badge" aria-label={`${messageUnread} tin chưa đọc`}>{messageUnread > 99 ? '99+' : messageUnread}</span>}</span>
      <span>{label}</span>
    </Link>)}
  </nav>
}
