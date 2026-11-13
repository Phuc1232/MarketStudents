import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errText, timeAgo, toast, useAuth } from '../../lib/api'
import { useRealtime } from '../../providers/RealtimeProvider'

export interface NotificationItem {
  notification_id: number
  title: string
  message?: string | null
  action_link?: string | null
  is_read: boolean
  created_at?: string | null
}

/** Reject protocol-relative URLs and browser-normalized external destinations. */
export function notificationLink(link?: string | null): string | null {
  if (!link || !link.startsWith('/') || link.startsWith('//') || /[\\\u0000-\u001f]/.test(link)) return null
  try {
    const url = new URL(link, window.location.origin)
    return url.origin === window.location.origin ? url.pathname + url.search + url.hash : null
  } catch { return null }
}

const PAGE_SIZE = 20

export default function Notifications() {
  const nav = useNavigate()
  const { token } = useAuth()
  const { notificationUnread, refresh } = useRealtime()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const request = useRef(0)

  useEffect(() => { setPage(1); setItems([]) }, [token])
  useEffect(() => {
    const reload = () => setRevision((n) => n + 1)
    window.addEventListener('cm:notification', reload)
    return () => window.removeEventListener('cm:notification', reload)
  }, [])
  useEffect(() => {
    const current = ++request.current
    setLoading(true); setError('')
    api.get<NotificationItem[]>('/interaction/notifications/me', { page, page_size: PAGE_SIZE })
      .then((list) => { if (request.current === current) setItems(list) })
      .catch((e) => { if (request.current === current) setError(errText(e)) })
      .finally(() => { if (request.current === current) setLoading(false) })
    return () => { request.current++ }
  }, [page, revision, token])

  const open = async (n: NotificationItem) => {
    if (busy) return
    setBusy(true)
    try {
      if (!n.is_read) {
        await api.patch(`/interaction/notifications/${n.notification_id}/read`)
        setItems((list) => list.map((x) => x.notification_id === n.notification_id ? { ...x, is_read: true } : x))
        await refresh()
        window.dispatchEvent(new Event('cm:notification'))
      }
      const link = notificationLink(n.action_link)
      if (link) nav(link)
    } catch (e) { toast(errText(e), 'err') }
    finally { setBusy(false) }
  }

  const readAll = async () => {
    setBusy(true)
    try {
      await api.patch('/interaction/notifications/read-all')
      setItems((list) => list.map((n) => ({ ...n, is_read: true })))
      await refresh()
      window.dispatchEvent(new Event('cm:notification'))
    } catch (e) { toast(errText(e), 'err') }
    finally { setBusy(false) }
  }

  return (
    <div className="container-narrow page">
      <div className="page-head">
        <div><h1>Thông báo</h1><p>{notificationUnread ? `${notificationUnread} thông báo chưa đọc` : 'Bạn đã xem hết rồi.'}</p></div>
        {notificationUnread > 0 && <button className="btn btn-soft" disabled={busy || loading} onClick={readAll}>Đánh dấu đã đọc tất cả</button>}
      </div>
      {error ? <div className="empty-box" role="alert"><span>{error}</span><button className="btn btn-soft" onClick={() => setRevision((n) => n + 1)}>Thử lại</button></div>
        : loading ? <div className="loading" role="status">Đang tải...</div> : items.length === 0 ? (
          <div className="empty-box"><strong>{page === 1 ? 'Chưa có thông báo' : 'Không còn thông báo cũ hơn'}</strong><span>Khi có bình luận, lượt theo dõi hay lời mời đánh giá, bạn sẽ thấy ở đây.</span></div>
        ) : (
          <div className="noti-list">
            {items.map((n) => (
              <button key={n.notification_id} className={`noti ${n.is_read ? 'read' : 'unread'}`} disabled={busy} onClick={() => open(n)}>
                <i className="noti-dot" aria-hidden="true" />
                <div><b>{n.title}</b>{n.message && <span>{n.message}</span>}<small>{n.is_read ? 'Đã đọc' : 'Chưa đọc'}{n.created_at ? ` · ${timeAgo(n.created_at)}` : ''}</small></div>
              </button>
            ))}
          </div>
        )}
      <nav className="noti-pagination" aria-label="Phân trang thông báo">
        <button className="btn btn-ghost" disabled={page <= 1 || loading || busy} onClick={() => setPage((n) => n - 1)}>Mới hơn</button>
        <span>Trang {page}</span>
        <button className="btn btn-ghost" disabled={items.length < PAGE_SIZE || loading || busy || !!error} onClick={() => setPage((n) => n + 1)}>Cũ hơn</button>
      </nav>
    </div>
  )
}
