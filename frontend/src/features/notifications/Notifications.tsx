import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errText, toast } from '../../lib/api'

interface N { notification_id: number; title: string; message?: string | null; action_link?: string | null; is_read: boolean }

export default function Notifications() {
  const nav = useNavigate()
  const [items, setItems] = useState<N[]>([])
  const [loading, setLoading] = useState(true)

  const syncBadge = (list: N[]) => window.dispatchEvent(new CustomEvent('cm:unread', { detail: list.filter((n) => !n.is_read).length }))

  useEffect(() => {
    const load = () => api.get<N[]>('/interaction/notifications/me').then((l) => { setItems([...l].sort((a, b) => b.notification_id - a.notification_id)) }).catch((e) => toast(errText(e), 'err')).finally(() => setLoading(false))
    load()
    window.addEventListener('cm:notification', load)
    return () => window.removeEventListener('cm:notification', load)
  }, [])

  const open = async (n: N) => {
    if (!n.is_read) {
      api.patch(`/interaction/notifications/${n.notification_id}/read`).catch(() => {})
      const next = items.map((x) => (x.notification_id === n.notification_id ? { ...x, is_read: true } : x))
      setItems(next); syncBadge(next)
    }
    // action_link do backend sinh ra; chỉ điều hướng nếu là đường dẫn nội bộ
    if (n.action_link && n.action_link.startsWith('/')) nav(n.action_link)
  }

  const readAll = async () => {
    try {
      await api.patch('/interaction/notifications/read-all')
      const next = items.map((x) => ({ ...x, is_read: true }))
      setItems(next); syncBadge(next)
    } catch (e) { toast(errText(e), 'err') }
  }

  const unread = items.filter((n) => !n.is_read).length

  return (
    <div className="container-narrow page">
      <div className="page-head">
        <div><h1>Thông báo</h1><p>{unread ? `${unread} thông báo chưa đọc` : 'Bạn đã xem hết rồi.'}</p></div>
        {unread > 0 && <button className="btn btn-soft" onClick={readAll}>Đánh dấu đã đọc tất cả</button>}
      </div>
      {loading ? <div className="loading">Đang tải...</div> : items.length === 0 ? (
        <div className="empty-box"><strong>Chưa có thông báo</strong><span>Khi có bình luận, lượt theo dõi hay lời mời đánh giá, bạn sẽ thấy ở đây.</span></div>
      ) : (
        <div className="noti-list">
          {items.map((n) => (
            <button key={n.notification_id} className={`noti ${n.is_read ? 'read' : 'unread'}`} onClick={() => open(n)}>
              <i className="noti-dot" />
              <div><b>{n.title}</b>{n.message && <span>{n.message}</span>}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
