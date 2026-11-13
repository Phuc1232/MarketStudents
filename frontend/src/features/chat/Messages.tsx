import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, ApiError, errText, fmtPrice, mediaUrl, Paginated, toast, useAuth, wsUrl } from '../../lib/api'

interface Msg { message_id: number; conversation_id: number; sender_id: number; content: string; is_read: boolean; sent_at: string; attachments: { attachment_id: number; file_url: string }[] }
interface Conv {
  conversation_id: number
  product: { product_id: number; title: string; price: number; thumbnail_url?: string | null }
  partner: { user_id: number; full_name: string }
  last_message?: Msg | null
  unread_count: number
}
interface Receipt { conversation_id: number; reader_id: number; last_read_message_id?: number }
interface Outgoing { id: number; conversation_id: number; content: string; attachments?: string[]; status: 'sending' | 'failed'; error?: string }

const PAGE = 50
const hhmm = (iso: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z').toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
const canSee = () => document.visibilityState === 'visible' && document.hasFocus()
const refreshCount = () => window.dispatchEvent(new Event('cm:chat-count-refresh'))

// Merge both realtime channels and REST history without reverting read flags.
function mergeMessages(old: Msg[], incoming: Msg[], readThrough = 0, userId: number | null = null) {
  const byId = new Map(old.map((m) => [m.message_id, m]))
  incoming.forEach((m) => byId.set(m.message_id, { ...m, is_read: m.is_read || !!byId.get(m.message_id)?.is_read || (m.sender_id === userId && m.message_id <= readThrough) }))
  return [...byId.values()].sort((a, b) => a.message_id - b.message_id)
}

export default function Messages() {
  const { userId, token } = useAuth()
  const [sp, setSp] = useSearchParams()
  const active = Number(sp.get('c')) || 0
  const [convs, setConvs] = useState<Conv[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState('')
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [hasOlder, setHasOlder] = useState(false)
  const [olderLoading, setOlderLoading] = useState(false)
  const [drafts, setDrafts] = useState<Record<number, string>>({})
  const [outgoing, setOutgoing] = useState<Outgoing[]>([])
  const [uploading, setUploading] = useState(false)
  const [live, setLive] = useState(false)
  const [readError, setReadError] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const messagesRef = useRef<Msg[]>([])
  const activeRef = useRef(active)
  const accountRef = useRef(token)
  const mountedRef = useRef(true)
  const listRequest = useRef(0)
  const requestId = useRef(0)
  const inFlight = useRef(new Set<number>())
  const nearBottom = useRef(true)
  const readRequested = useRef(0)
  const readAcknowledged = useRef(0)
  const partnerReadThrough = useRef(0)
  const syncRef = useRef<() => void>(() => {})
  activeRef.current = active
  accountRef.current = token
  messagesRef.current = msgs
  const text = drafts[active] ?? ''
  const conv = convs.find((c) => c.conversation_id === active)

  const loadConvs = useCallback(async () => {
    const sequence = ++listRequest.current
    const account = token
    try {
      const result = await api.get<Conv[]>('/interaction/conversations')
      if (mountedRef.current && accountRef.current === account && sequence === listRequest.current) { setConvs(result); setListError('') }
    } catch (e) {
      if (mountedRef.current && accountRef.current === account && sequence === listRequest.current) setListError(errText(e))
    } finally {
      if (mountedRef.current && accountRef.current === account && sequence === listRequest.current) setLoading(false)
    }
  }, [token])

  useEffect(() => {
    mountedRef.current = true
    setConvs([]); setLoading(true); setDrafts({}); setOutgoing([])
    loadConvs()
    const interval = window.setInterval(() => { if (canSee()) loadConvs() }, 30000)
    return () => { mountedRef.current = false; ++listRequest.current; window.clearInterval(interval) }
  }, [loadConvs])

  const markVisibleRead = useCallback(() => {
    if (!active || activeRef.current !== active || !scrollRef.current || !canSee() || !nearBottom.current) return
    const incoming = messagesRef.current.filter((m) => m.sender_id !== userId)
    const lastId = incoming.length ? incoming[incoming.length - 1].message_id : 0
    if (!lastId || lastId <= readRequested.current) return
    readRequested.current = lastId
    const account = token
    api.patch(`/interaction/conversations/${active}/read`, undefined, { last_read_message_id: lastId }).then(() => {
      if (!mountedRef.current || accountRef.current !== account || activeRef.current !== active) return
      readAcknowledged.current = Math.max(readAcknowledged.current, lastId)
      setReadError('')
      setMsgs((old) => old.map((m) => m.sender_id !== userId && m.message_id <= lastId ? { ...m, is_read: true } : m))
      loadConvs(); refreshCount()
    }).catch(() => {
      if (!mountedRef.current || accountRef.current !== account || activeRef.current !== active) return
      readRequested.current = readAcknowledged.current
      setReadError('Chưa cập nhật được trạng thái đã đọc.')
    })
  }, [active, userId, token, loadConvs])

  useEffect(() => {
    let dead = false
    let socket: WebSocket | null = null
    let ping: number | undefined
    let retry: number | undefined
    let listTimer: number | undefined
    let retryDelay = 1000
    let syncing = false
    let syncAgain = false
    let syncedThrough = 0
    setMsgs([]); messagesRef.current = []; setLive(false); setHasOlder(false); setHistoryError(''); setReadError(''); setOlderLoading(false)
    nearBottom.current = true
    readRequested.current = 0; readAcknowledged.current = 0; partnerReadThrough.current = 0
    const updateList = () => {
      window.clearTimeout(listTimer)
      listTimer = window.setTimeout(() => { if (!dead) loadConvs() }, 150)
    }
    const merge = (items: Msg[]) => {
      if (dead) return
      setMsgs((old) => mergeMessages(old, items.filter((m) => m.conversation_id === active), partnerReadThrough.current, userId))
    }
    const receive = (m: Msg) => {
      if (dead || !m?.message_id) return
      if (m.conversation_id === active) merge([m])
      updateList()
    }
    const receipt = (r: Receipt) => {
      if (dead || !r) return
      if (r.conversation_id === active && r.reader_id !== userId && typeof r.last_read_message_id === 'number') {
        partnerReadThrough.current = Math.max(partnerReadThrough.current, r.last_read_message_id)
        setMsgs((old) => old.map((m) => m.sender_id === userId && m.message_id <= partnerReadThrough.current ? { ...m, is_read: true } : m))
      }
      updateList()
    }
    const sync = async () => {
      if (!active || dead) return
      if (syncing) { syncAgain = true; return }
      syncing = true
      setHistoryLoading(true)
      // Only REST advances this cursor. A new realtime event arriving first
      // after reconnect must not skip older messages missed during the outage.
      let cursor = syncedThrough
      try {
        if (!cursor) {
          const page = await api.get<Paginated<Msg>>(`/interaction/conversations/${active}/messages`, { page_size: PAGE, newest_first: true })
          if (dead) return
          merge(page.items); setHasOlder(page.total > page.items.length)
          syncedThrough = Math.max(0, ...page.items.map((m) => m.message_id))
        } else {
          while (!dead) {
            const page = await api.get<Paginated<Msg>>(`/interaction/conversations/${active}/messages`, { page_size: PAGE, newest_first: false, after_id: cursor })
            if (dead) return
            merge(page.items)
            const next = Math.max(cursor, ...page.items.map((m) => m.message_id))
            syncedThrough = next
            if (page.items.length < PAGE || next === cursor) break
            cursor = next
          }
          const latest = await api.get<Paginated<Msg>>(`/interaction/conversations/${active}/messages`, { page_size: PAGE, newest_first: true })
          if (!dead) merge(latest.items)
        }
        if (!dead) { setHistoryError(''); markVisibleRead() }
      } catch (e) { if (!dead) setHistoryError(errText(e)) }
      finally {
        syncing = false
        if (!dead) {
          setHistoryLoading(false)
          if (syncAgain) { syncAgain = false; void sync() }
        }
      }
    }
    syncRef.current = () => { void sync(); loadConvs() }
    const messageEvent = (e: Event) => receive((e as CustomEvent<Msg>).detail)
    const readEvent = (e: Event) => receipt((e as CustomEvent<Receipt>).detail)
    const resync = () => { if (!dead && canSee()) { void sync(); updateList(); markVisibleRead() } }
    window.addEventListener('cm:chat-message', messageEvent)
    window.addEventListener('cm:chat-read', readEvent)
    window.addEventListener('cm:realtime-sync', resync)
    window.addEventListener('focus', resync)
    document.addEventListener('visibilitychange', resync)
    if (active) {
      void sync()
      const connect = () => {
        if (dead) return
        const ws = new WebSocket(wsUrl(`/interaction/ws/chat/${active}`))
        socket = ws
        ws.onopen = () => {
          if (dead) { ws.close(); return }
          setLive(true); retryDelay = 1000; void sync()
          ping = window.setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ action: 'ping' })) }, 25000)
        }
        ws.onmessage = (ev) => {
          if (dead) return
          try {
            const event = JSON.parse(ev.data)
            if (event.type === 'new_message') receive(event.data)
            else if (event.type === 'read_receipt') receipt(event.data)
          } catch { /* REST remains authoritative. */ }
        }
        ws.onclose = (e) => {
          window.clearInterval(ping)
          if (dead) return
          setLive(false)
          if (e.code !== 4401 && e.code !== 4403) {
            retry = window.setTimeout(connect, retryDelay)
            retryDelay = Math.min(retryDelay * 2, 30000)
          }
        }
      }
      connect()
    }
    return () => {
      dead = true; window.clearInterval(ping); window.clearTimeout(retry); window.clearTimeout(listTimer); socket?.close()
      window.removeEventListener('cm:chat-message', messageEvent)
      window.removeEventListener('cm:chat-read', readEvent)
      window.removeEventListener('cm:realtime-sync', resync)
      window.removeEventListener('focus', resync)
      document.removeEventListener('visibilitychange', resync)
    }
  }, [active, userId, token, loadConvs, markVisibleRead])

  const lastMessageId = msgs.length ? msgs[msgs.length - 1].message_id : 0
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      if (nearBottom.current) { endRef.current?.scrollIntoView({ block: 'end' }); markVisibleRead() }
    })
    return () => cancelAnimationFrame(frame)
  }, [lastMessageId, active, conv?.conversation_id, markVisibleRead])

  const loadOlder = async () => {
    if (!msgs.length || olderLoading) return
    const conversation = active
    const account = token
    const pane = scrollRef.current
    const height = pane?.scrollHeight ?? 0
    const top = pane?.scrollTop ?? 0
    setOlderLoading(true)
    try {
      const page = await api.get<Paginated<Msg>>(`/interaction/conversations/${active}/messages`, { page_size: PAGE, newest_first: true, before_id: msgs[0].message_id })
      if (!mountedRef.current || activeRef.current !== conversation || accountRef.current !== account) return
      nearBottom.current = false
      setMsgs((old) => mergeMessages(old, page.items, partnerReadThrough.current, userId))
      setHasOlder(page.items.length === PAGE); setHistoryError('')
      requestAnimationFrame(() => { if (pane && activeRef.current === conversation) pane.scrollTop = top + pane.scrollHeight - height })
    } catch (e) { if (mountedRef.current && activeRef.current === conversation && accountRef.current === account) setHistoryError(errText(e)) }
    finally { if (mountedRef.current && activeRef.current === conversation && accountRef.current === account) setOlderLoading(false) }
  }

  const deliver = async (item: Outgoing) => {
    if (inFlight.current.has(item.id)) return
    inFlight.current.add(item.id)
    const account = token
    setOutgoing((old) => old.map((m) => m.id === item.id ? { ...m, status: 'sending', error: undefined } : m))
    try {
      const message = await api.post<Msg>(`/interaction/conversations/${item.conversation_id}/messages`, { content: item.content, attachments: item.attachments })
      if (!mountedRef.current || accountRef.current !== account) return
      setOutgoing((old) => old.filter((m) => m.id !== item.id))
      if (activeRef.current === item.conversation_id) {
        nearBottom.current = true
        setMsgs((old) => mergeMessages(old, [message], partnerReadThrough.current, userId))
      }
      loadConvs()
    } catch (e) {
      if (!mountedRef.current || accountRef.current !== account) return
      const uncertain = e instanceof ApiError && (e.status === 0 || e.status >= 500)
      const error = uncertain ? 'Chưa xác nhận gửi thành công. Kiểm tra tin nhắn phía trên trước khi gửi lại để tránh gửi trùng.' : errText(e)
      setOutgoing((old) => old.map((m) => m.id === item.id ? { ...m, status: 'failed', error } : m))
      if (activeRef.current === item.conversation_id) syncRef.current()
    } finally { inFlight.current.delete(item.id) }
  }
  const queue = (conversation: number, content: string, attachments?: string[]) => {
    const item: Outgoing = { id: ++requestId.current, conversation_id: conversation, content, attachments, status: 'sending' }
    setOutgoing((old) => [...old, item]); void deliver(item)
    if (activeRef.current === conversation) {
      nearBottom.current = true
      requestAnimationFrame(() => { if (activeRef.current === conversation) endRef.current?.scrollIntoView({ block: 'end' }) })
    }
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim() || !active) return
    queue(active, text.trim())
    setDrafts((old) => ({ ...old, [active]: '' }))
  }
  const attach = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !active) return
    const conversation = active
    const account = token
    setUploading(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const result = await api.upload<{ detail_url?: string; image_url: string }>('/upload/image', fd)
      if (mountedRef.current && accountRef.current === account) queue(conversation, '[Hình ảnh]', [result.detail_url || result.image_url])
    } catch (error) { if (mountedRef.current && accountRef.current === account) toast(errText(error), 'err') }
    finally { if (mountedRef.current && accountRef.current === account) setUploading(false) }
  }
  return (
    <div className="container page chat-page">
      <div className="page-head"><div><h1>Tin nhắn</h1></div></div>
      <div className={`chat${active ? ' open' : ''}`}>
        <aside className="chat-list" aria-label="Danh sách hội thoại">
          {listError && <div className="chat-alert" role="alert">{listError} <button onClick={() => loadConvs()}>Thử lại</button></div>}
          {loading ? <div className="loading">Đang tải...</div> : convs.length === 0 ? (
            <div className="chat-empty"><div><p>Chưa có cuộc trò chuyện nào.</p><p className="hint">Mở một tin đăng và bấm “Nhắn tin cho người bán”.</p></div></div>
          ) : convs.map((c) => (
            <button key={c.conversation_id} className={`conv${c.conversation_id === active ? ' on' : ''}`} onClick={() => setSp({ c: String(c.conversation_id) })} aria-current={c.conversation_id === active ? 'true' : undefined}>
              <span className="conv-img">{c.product.thumbnail_url ? <img src={mediaUrl(c.product.thumbnail_url)} alt="" /> : <Icon name="image" size={18} />}</span>
              <span className="conv-body"><b>{c.partner.full_name}</b><small className="conv-prod">{c.product.title}</small><small>{c.last_message?.content ?? 'Chưa có tin nhắn'}</small></span>
              {c.unread_count > 0 && <span className="conv-unread" aria-label={`${c.unread_count} tin chưa đọc`}>{c.unread_count > 99 ? '99+' : c.unread_count}</span>}
            </button>
          ))}
        </aside>
        <section className="chat-pane">
          {!active || !conv ? (
            <div className="chat-empty"><div><Icon name="chat" size={40} /><p>{active && loading ? 'Đang tải hội thoại...' : active ? 'Không tìm thấy hội thoại. Hãy chọn một cuộc trò chuyện khác.' : 'Chọn một cuộc trò chuyện để bắt đầu.'}</p>{active > 0 && <button className="btn btn-soft" onClick={() => setSp({})}>Danh sách hội thoại</button>}</div></div>
          ) : (
            <>
              <div className="chat-head">
                <button className="back" onClick={() => setSp({})} aria-label="Quay lại"><Icon name="back" size={22} /></button>
                <span className="avatar">{conv.partner.full_name.slice(0, 1).toUpperCase()}</span>
                <div className="who"><b>{conv.partner.full_name}</b><span className={`conn${live ? ' live' : ''}`}><i /> {live ? 'Đã kết nối' : 'Đang kết nối lại...'}</span></div>
                <Link to={`/product?id=${conv.product.product_id}`} className="chat-prod"><span className="conv-img">{conv.product.thumbnail_url ? <img src={mediaUrl(conv.product.thumbnail_url)} alt="" /> : <Icon name="image" size={14} />}</span><div><span>{conv.product.title}</span><i>{fmtPrice(conv.product.price)}</i></div></Link>
              </div>
              {historyError && <div className="chat-alert" role="alert">{historyError} <button onClick={() => syncRef.current()}>Thử lại</button></div>}
              {readError && <div className="chat-alert" role="status">{readError} <button onClick={markVisibleRead}>Thử lại</button></div>}
              <div className="chat-msgs" ref={scrollRef} onScroll={() => {
                const pane = scrollRef.current
                nearBottom.current = !!pane && pane.scrollHeight - pane.scrollTop - pane.clientHeight < 70
                if (nearBottom.current) markVisibleRead()
              }}>
                {hasOlder && <button type="button" className="chat-load-older" disabled={olderLoading} onClick={loadOlder}>{olderLoading ? 'Đang tải...' : 'Xem tin nhắn cũ hơn'}</button>}
                {historyLoading && msgs.length === 0 && <div className="loading">Đang tải tin nhắn...</div>}
                {msgs.map((m) => (
                  <div key={m.message_id} className={`msg${m.sender_id === userId ? ' me' : ''}`}>
                    {!(m.attachments.length && m.content === '[Hình ảnh]') && m.content}
                    {m.attachments.map((a) => <a key={a.attachment_id} href={mediaUrl(a.file_url)} target="_blank" rel="noreferrer"><img src={mediaUrl(a.file_url)} alt="Hình đính kèm" /></a>)}
                    <time>{hhmm(m.sent_at)}{m.sender_id === userId ? m.is_read ? ' · Đã xem' : ' · Đã gửi' : ''}</time>
                  </div>
                ))}
                {outgoing.filter((m) => m.conversation_id === active).map((m) => (
                  <div key={`outgoing-${m.id}`} className={`msg me msg-${m.status}`}>
                    {m.content !== '[Hình ảnh]' && m.content}
                    {m.attachments?.map((url) => <img key={url} src={mediaUrl(url)} alt="Ảnh đang gửi" />)}
                    <time>{m.status === 'sending' ? 'Đang gửi...' : 'Chưa gửi thành công'}</time>
                    {m.status === 'failed' && <div className="msg-retry"><span>{m.error}</span><button onClick={() => void deliver(m)}>Gửi lại</button><button onClick={() => setOutgoing((old) => old.filter((x) => x.id !== m.id))}>Bỏ qua</button></div>}
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <form className="chat-form" onSubmit={submit}>
                <button type="button" className="icon-btn" disabled={uploading} onClick={() => fileRef.current?.click()} aria-label={uploading ? 'Đang tải ảnh' : 'Gửi ảnh'}><Icon name="image" size={20} /></button>
                <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={attach} />
                <input className="input" value={text} onChange={(e) => setDrafts((old) => ({ ...old, [active]: e.target.value }))} maxLength={2000} placeholder="Nhập tin nhắn..." aria-label="Nhập tin nhắn" />
                <button className="icon-btn send" aria-label="Gửi" disabled={!text.trim()}><Icon name="send" size={18} /></button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
