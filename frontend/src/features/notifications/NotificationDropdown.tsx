import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, errText, timeAgo, toast, useAuth } from '../../lib/api'
import { useRealtime } from '../../providers/RealtimeProvider'
import { NotificationItem, notificationLink } from './Notifications'

export default function NotificationDropdown() {
  const { token } = useAuth()
  const { notificationUnread, refresh } = useRealtime()
  const nav = useNavigate()
  const location = useLocation()
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)

  useEffect(() => { setOpen(false); setItems([]) }, [location.pathname, location.search, token])
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); trigger.current?.focus() } }
    const reload = () => setRevision((n) => n + 1)
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    window.addEventListener('cm:notification', reload)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
      window.removeEventListener('cm:notification', reload)
    }
  }, [open])
  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true); setError('')
    api.get<NotificationItem[]>('/interaction/notifications/me', { page: 1, page_size: 5 })
      .then((list) => { if (!cancelled) setItems(list) })
      .catch((e) => { if (!cancelled) setError(errText(e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [open, revision, token])

  const openItem = async (item: NotificationItem) => {
    if (busy) return
    setBusy(true)
    try {
      if (!item.is_read) {
        await api.patch(`/interaction/notifications/${item.notification_id}/read`)
        await refresh()
        window.dispatchEvent(new Event('cm:notification'))
      }
      const link = notificationLink(item.action_link)
      if (link) { setOpen(false); nav(link) }
    } catch (e) { toast(errText(e), 'err') }
    finally { setBusy(false) }
  }

  if (!token) return null
  return (
    <div className="noti-dropdown" ref={root}>
      <button ref={trigger} type="button" className="nav-icon noti-trigger" aria-label={`Thông báo, ${notificationUnread} chưa đọc`} aria-expanded={open} aria-controls="notification-popover" aria-haspopup="dialog" onClick={() => setOpen((value) => !value)}>
        <Icon name="bell" size={21} /><span className="noti-label">Thông báo</span>
        {notificationUnread > 0 && <span className="nav-badge" aria-hidden="true">{notificationUnread > 99 ? '99+' : notificationUnread}</span>}
      </button>
      {open && <section className="noti-popover" id="notification-popover" role="dialog" aria-labelledby="notification-heading">
        <div className="noti-popover-head"><strong id="notification-heading">Thông báo</strong><button type="button" className="icon-btn" aria-label="Đóng thông báo" onClick={() => { setOpen(false); trigger.current?.focus() }}><Icon name="x" size={18} /></button></div>
        <p className="hint">{notificationUnread ? `${notificationUnread} thông báo chưa đọc` : 'Bạn đã xem hết rồi.'}</p>
        {loading ? <p role="status">Đang tải...</p> : error ? <div role="alert"><p>{error}</p><button className="btn btn-soft btn-sm" onClick={() => setRevision((n) => n + 1)}>Thử lại</button></div> : items.length === 0 ? <p>Chưa có thông báo.</p> : <div className="noti-list">{items.map((item) => (
          <button key={item.notification_id} className={`noti ${item.is_read ? 'read' : 'unread'}`} disabled={busy} onClick={() => openItem(item)}>
            <i className="noti-dot" aria-hidden="true" /><div><b>{item.title}</b>{item.message && <span>{item.message}</span>}<small>{item.is_read ? 'Đã đọc' : 'Chưa đọc'}{item.created_at ? ` · ${timeAgo(item.created_at)}` : ''}</small></div>
          </button>
        ))}</div>}
        <Link to="/notifications" className="noti-view-all" onClick={() => setOpen(false)}>Xem tất cả thông báo</Link>
      </section>}
    </div>
  )
}
