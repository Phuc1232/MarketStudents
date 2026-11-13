import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { mediaUrl } from '../../lib/api'
import { useRealtime } from '../../providers/RealtimeProvider'
import Icon from './Icon'

export default function MessageNotification() {
  const { alerts, dismiss } = useRealtime()
  const loc = useLocation()
  useEffect(() => {
    if (/^\/messages(?:\.html)?\/?$/.test(loc.pathname)) dismiss(Number(new URLSearchParams(loc.search).get('c')))
  }, [loc.pathname, loc.search, dismiss])
  return <aside className="message-alerts" aria-label="Tin nhắn mới" aria-live="polite" aria-relevant="additions text">
    {alerts.map(({ message: m, count }) => <div className="message-alert" key={m.conversation_id}>
      <button className="message-alert-close" onClick={() => dismiss(m.conversation_id)} aria-label="Đóng thông báo tin nhắn"><Icon name="x" size={17} /></button>
      <Link to={`/messages?c=${m.conversation_id}`} onClick={() => dismiss(m.conversation_id)} className="message-alert-link">
        <span className="message-alert-avatar">{m.sender?.avatar_url ? <img src={mediaUrl(m.sender.avatar_url)} alt="" /> : <Icon name="chat" size={22} />}</span>
        <span className="message-alert-body">
          <small>Tin nhắn mới{count > 1 ? ` · ${count} tin` : ''}</small>
          <strong>{m.sender?.full_name ?? 'Người dùng'}</strong>
          {m.product?.title && <span className="message-alert-product">{m.product.title}</span>}
          <span className="message-alert-preview">{m.content === '[Hình ảnh]' ? 'Đã gửi một hình ảnh' : m.content}</span>
          <b>Mở hội thoại <Icon name="arrow" size={14} /></b>
        </span>
      </Link>
    </div>)}
  </aside>
}
