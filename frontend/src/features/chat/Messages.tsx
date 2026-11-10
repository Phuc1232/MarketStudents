import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, errText, fmtPrice, mediaUrl, Paginated, toast, useAuth, wsUrl } from '../../lib/api'

interface Msg { message_id: number; conversation_id: number; sender_id: number; content: string; is_read: boolean; sent_at: string; attachments: { attachment_id: number; file_url: string }[] }
interface Conv {
  conversation_id: number
  product: { product_id: number; title: string; price: number; thumbnail_url?: string | null }
  partner: { user_id: number; full_name: string }
  last_message?: Msg | null
  unread_count: number
}

const PAGE = 50
const hhmm = (iso: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z').toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })

export default function Messages() {
  const { userId } = useAuth()
  const [sp, setSp] = useSearchParams()
  const active = Number(sp.get('c')) || 0
  const [convs, setConvs] = useState<Conv[]>([])
  const [loading, setLoading] = useState(true)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [text, setText] = useState('')
  const [live, setLive] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadConvs = useCallback(() => {
    api.get<Conv[]>('/interaction/conversations').then(setConvs).catch((e) => toast(errText(e), 'err')).finally(() => setLoading(false))
  }, [])
  useEffect(() => { loadConvs(); const t = setInterval(loadConvs, 20000); return () => clearInterval(t) }, [loadConvs])

  const conv = convs.find((c) => c.conversation_id === active)

  // Tải lịch sử + mở WebSocket khi đổi cuộc hội thoại
  useEffect(() => {
    setMsgs([]); setLive(false)
    if (!active) return
    let dead = false
    ;(async () => {
      try {
        const first = await api.get<Paginated<Msg>>(`/interaction/conversations/${active}/messages`, { page: 1, page_size: PAGE })
        let all = first.items
        const pages = Math.min(Math.ceil(first.total / PAGE), 10)
        for (let p = 2; p <= pages; p++) all = all.concat((await api.get<Paginated<Msg>>(`/interaction/conversations/${active}/messages`, { page: p, page_size: PAGE })).items)
        if (!dead) setMsgs(all.sort((a, b) => a.message_id - b.message_id))
        api.patch(`/interaction/conversations/${active}/read`).then(() => setConvs((cs) => cs.map((c) => c.conversation_id === active ? { ...c, unread_count: 0 } : c))).catch(() => {})
      } catch (e) { toast(errText(e), 'err') }
    })()

    let ping: number | undefined
    let retry: number | undefined
    const connect = () => {
      const ws = new WebSocket(wsUrl(`/interaction/ws/chat/${active}`))
      wsRef.current = ws
      ws.onopen = () => { setLive(true); ping = window.setInterval(() => ws.readyState === 1 && ws.send(JSON.stringify({ action: 'ping' })), 25000) }
      ws.onmessage = (ev) => {
        try {
          const m = JSON.parse(ev.data)
          if (m.type === 'new_message') {
            const d: Msg = m.data
            setMsgs((old) => (old.some((x) => x.message_id === d.message_id) ? old : [...old, d]))
            setConvs((cs) => cs.map((c) => c.conversation_id === d.conversation_id ? { ...c, last_message: d } : c))
            if (d.sender_id !== userId && ws.readyState === 1) ws.send(JSON.stringify({ action: 'mark_read' }))
          } else if (m.type === 'read_receipt' && m.data.reader_id !== userId) {
            setMsgs((old) => old.map((x) => (x.sender_id === userId ? { ...x, is_read: true } : x)))
          } else if (m.type === 'error') toast(m.message, 'err')
        } catch { /* bỏ qua */ }
      }
      ws.onclose = (e) => {
        window.clearInterval(ping); setLive(false)
        if (!dead && e.code !== 4401 && e.code !== 4403) retry = window.setTimeout(connect, 3000)
      }
    }
    connect()
    return () => { dead = true; window.clearInterval(ping); window.clearTimeout(retry); wsRef.current?.close(); wsRef.current = null }
  }, [active, userId])

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [msgs.length, active])

  const send = async (content: string, attachments?: string[]) => {
    const ws = wsRef.current
    if (ws && ws.readyState === 1) {
      ws.send(JSON.stringify({ action: 'send_message', content, attachments }))
    } else {
      try {
        const m = await api.post<Msg>(`/interaction/conversations/${active}/messages`, { content, attachments })
        setMsgs((o) => [...o, m])
      } catch (e) { toast(errText(e), 'err') }
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const c = text.trim()
    if (!c || !active) return
    setText(''); send(c)
  }

  const attach = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await api.upload<{ detail_url?: string; image_url: string }>('/upload/image', fd)
      send('[Hình ảnh]', [r.detail_url || r.image_url])
    } catch (e2) { toast(errText(e2), 'err') }
  }

  const open = (id: number) => setSp({ c: String(id) })

  return (
    <div className="container page">
      <div className="page-head"><div><h1>Tin nhắn</h1></div></div>
      <div className={`chat${active ? ' open' : ''}`}>
        <aside className="chat-list" aria-label="Danh sách hội thoại">
          {loading ? <div className="loading">Đang tải...</div> : convs.length === 0 ? (
            <div className="chat-empty"><div><p>Chưa có cuộc trò chuyện nào.</p><p className="hint">Mở một tin đăng và bấm “Nhắn tin cho người bán”.</p></div></div>
          ) : convs.map((c) => (
            <button key={c.conversation_id} className={`conv${c.conversation_id === active ? ' on' : ''}`} onClick={() => open(c.conversation_id)}>
              <span className="conv-img">{c.product.thumbnail_url ? <img src={mediaUrl(c.product.thumbnail_url)} alt="" /> : <Icon name="image" size={18} />}</span>
              <span className="conv-body">
                <b>{c.partner.full_name}</b>
                <small className="conv-prod">{c.product.title}</small>
                <small>{c.last_message?.content ?? 'Chưa có tin nhắn'}</small>
              </span>
              {c.unread_count > 0 && <span className="conv-unread">{c.unread_count}</span>}
            </button>
          ))}
        </aside>

        <section className="chat-pane">
          {!active || !conv ? (
            <div className="chat-empty"><div><Icon name="chat" size={40} /><p>Chọn một cuộc trò chuyện để bắt đầu.</p></div></div>
          ) : (
            <>
              <div className="chat-head">
                <button className="back" onClick={() => setSp({})} aria-label="Quay lại"><Icon name="back" size={22} /></button>
                <span className="avatar">{conv.partner.full_name.slice(0, 1).toUpperCase()}</span>
                <div className="who"><b>{conv.partner.full_name}</b><span className={`conn${live ? ' live' : ''}`}><i /> {live ? 'Đang kết nối' : 'Đang kết nối lại...'}</span></div>
                <Link to={`/product?id=${conv.product.product_id}`} className="chat-prod">
                  <span className="conv-img">{conv.product.thumbnail_url ? <img src={mediaUrl(conv.product.thumbnail_url)} alt="" /> : <Icon name="image" size={14} />}</span>
                  <div><span>{conv.product.title}</span><i>{fmtPrice(conv.product.price)}</i></div>
                </Link>
              </div>
              <div className="chat-msgs">
                {msgs.map((m) => (
                  <div key={m.message_id} className={`msg${m.sender_id === userId ? ' me' : ''}`}>
                    {!(m.attachments.length && m.content === '[Hình ảnh]') && m.content}
                    {m.attachments.map((a) => <a key={a.attachment_id} href={mediaUrl(a.file_url)} target="_blank" rel="noreferrer"><img src={mediaUrl(a.file_url)} alt="Hình đính kèm" /></a>)}
                    <time>{hhmm(m.sent_at)}{m.sender_id === userId && m.is_read ? ' · Đã xem' : ''}</time>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <form className="chat-form" onSubmit={submit}>
                <button type="button" className="icon-btn" onClick={() => fileRef.current?.click()} aria-label="Gửi ảnh"><Icon name="image" size={20} /></button>
                <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={attach} />
                <input className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} placeholder="Nhập tin nhắn..." aria-label="Nhập tin nhắn" />
                <button className="icon-btn send" aria-label="Gửi" disabled={!text.trim()}><Icon name="send" size={18} /></button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
