import ProductActions from '../../components/ui/ProductActions'
import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, CONDITIONS, errText, fmtPrice, mediaUrl, Paginated, ProductDetail, ProductListItem, STATUSES, timeAgo, toast } from '../../lib/api'

type Tab = 'selling' | 'trash' | 'bought'
interface Trash { product_id: number; title: string; price: number; thumbnails?: string | null; remaining_days: number; can_restore: boolean }
interface Bought { product_id: number; title: string; price: number; thumbnail_url?: string | null; seller: { user_id: number; full_name: string }; purchased_at: string; has_reviewed: boolean }
interface Buyer { user_id: number; full_name: string }

function Thumb({ src }: { src?: string | null }) {
  const u = mediaUrl(src)
  return <span className="row-thumb">{u ? <img src={u} alt="" /> : <Icon name="image" size={22} />}</span>
}

export default function MyProducts() {
  const [search, setSearch] = useSearchParams()
  const reviewId = Number(search.get('review')) || 0
  const requestedTab = search.get('tab')
  const tab: Tab = reviewId > 0 || requestedTab === 'bought' ? 'bought' : requestedTab === 'trash' ? 'trash' : 'selling'
  const setTab = (next: Tab) => setSearch({ tab: next })
  const [selling, setSelling] = useState<ProductListItem[]>([])
  const [trash, setTrash] = useState<Trash[]>([])
  const [bought, setBought] = useState<Bought[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<ProductDetail | null>(null)
  const [soldFor, setSoldFor] = useState<ProductListItem | null>(null)
  const [reviewFor, setReviewFor] = useState<Bought | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)

  const load = useCallback(async (t: Tab) => {
    setLoading(true)
    try {
      if (t === 'selling') setSelling(await api.get<ProductListItem[]>('/product/me'))
      if (t === 'trash') setTrash((await api.get<Paginated<Trash>>('/product/me/trash', { page: 1, page_size: 100 })).items)
      if (t === 'bought') setBought((await api.get<Paginated<Bought>>('/product/my-purchases', { page: 1, page_size: 100 })).items)
    } catch (e) { toast(errText(e), 'err') } finally { setLoading(false) }
  }, [])
  useEffect(() => { load(tab) }, [tab, load])

  // Resolve against the authenticated user's purchases before opening a review.
  // The target can be older than the first page of purchases.
  useEffect(() => {
    if (!Number.isSafeInteger(reviewId) || reviewId <= 0) { setReviewLoading(false); return }
    let cancelled = false
    setReviewFor(null); setReviewLoading(true)
    const clearTarget = () => setSearch((current) => {
      const next = new URLSearchParams(current)
      if (Number(next.get('review')) === reviewId) next.delete('review')
      return next
    }, { replace: true })
    ;(async () => {
      try {
        let page = 1
        let found: Bought | undefined
        while (!cancelled) {
          const result = await api.get<Paginated<Bought>>('/product/my-purchases', { page, page_size: 100 })
          if (cancelled) return
          found = result.items.find((item) => item.product_id === reviewId)
          if (found || !result.items.length || page * 100 >= result.total) break
          page++
        }
        if (cancelled) return
        if (!found) toast('Không tìm thấy món hàng này trong danh sách đã mua của bạn.', 'err')
        else if (found.has_reviewed) toast('Bạn đã đánh giá giao dịch này rồi.')
        else setReviewFor(found)
        clearTarget()
      } catch (e) {
        if (!cancelled) { toast(errText(e), 'err'); clearTarget() }
      } finally { if (!cancelled) setReviewLoading(false) }
    })()
    return () => { cancelled = true }
  }, [reviewId, setSearch])

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); toast(ok); load(tab) } catch (e) { toast(errText(e), 'err') }
  }

  const openEdit = async (id: number) => {
    try { setEditing(await api.get<ProductDetail>(`/product/${id}`)) } catch (e) { toast(errText(e), 'err') }
  }

  return (
    <div className="container page">
      <div className="page-head">
        <div><h1>Tin của tôi</h1><p>Quản lý tin đang bán, thùng rác và các món đã mua.</p></div>
        <Link to="/post" className="btn btn-primary"><Icon name="plus" size={18} /> Đăng tin mới</Link>
      </div>
      <div className="tabs" role="tablist">
        {([['selling', 'Đang đăng'], ['trash', 'Thùng rác'], ['bought', 'Đã mua']] as [Tab, string][]).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>

      <div className="mp-list">
        {reviewLoading && <div className="loading" role="status">Đang mở giao dịch cần đánh giá...</div>}
        {loading && <div className="loading">Đang tải...</div>}

        {!loading && tab === 'selling' && (selling.length === 0 ? (
          <div className="empty-box"><strong>Bạn chưa đăng tin nào</strong><Link to="/post" className="btn btn-primary">Đăng món đầu tiên</Link></div>
        ) : selling.map((p) => {
          const st = STATUSES[p.status_id]
          const canToggle = p.status_id === 2 || p.status_id === 4
          return (
            <div className="mp-row" key={p.product_id}>
              <Thumb src={p.thumbnails} />
              <div className="mp-main">
                <Link to={`/product?id=${p.product_id}`} className="mp-title">{p.title}</Link>
                <div className="mp-meta"><b>{fmtPrice(p.price)}</b><span>{CONDITIONS[p.condition_id]}</span><span><Icon name="eye" size={13} /> {p.view_count}</span><span>{timeAgo(p.CreatedAt)}</span></div>
              </div>
              {st && <span className={`badge badge-${st.tone}`}>{st.label}</span>}
              <ProductActions>
                {p.status_id !== 3 && <button className="btn btn-ghost btn-sm" onClick={() => openEdit(p.product_id)}><Icon name="edit" size={14} /> Sửa</button>}
                {canToggle && <button className="btn btn-ghost btn-sm" onClick={() => act(() => api.patch(`/product/${p.product_id}/toggle-hide`), p.status_id === 2 ? 'Đã tạm ẩn tin' : 'Tin đã hiển thị lại')}><Icon name={p.status_id === 2 ? 'eyeoff' : 'eye'} size={14} /> {p.status_id === 2 ? 'Ẩn' : 'Hiện'}</button>}
                {canToggle && <button className="btn btn-soft btn-sm" onClick={() => setSoldFor(p)}><Icon name="check" size={14} /> Đã bán</button>}
                <button className="btn btn-danger btn-sm" onClick={() => confirm('Chuyển tin vào thùng rác? Bạn có 30 ngày để khôi phục.') && act(() => api.del(`/product/${p.product_id}`), 'Đã chuyển vào thùng rác')} aria-label="Xóa"><Icon name="trash" size={14} /></button>
              </ProductActions>
            </div>
          )
        }))}

        {!loading && tab === 'trash' && (trash.length === 0 ? (
          <div className="empty-box"><strong>Thùng rác trống</strong><span>Tin đã xóa được giữ lại 30 ngày.</span></div>
        ) : trash.map((p) => (
          <div className="mp-row" key={p.product_id}>
            <Thumb src={p.thumbnails} />
            <div className="mp-main"><span className="mp-title">{p.title}</span><div className="mp-meta"><b>{fmtPrice(p.price)}</b><span>Còn {p.remaining_days} ngày trước khi xóa vĩnh viễn</span></div></div>
            <div className="mp-actions">
              {p.can_restore && <button className="btn btn-soft btn-sm" onClick={() => act(() => api.post(`/product/${p.product_id}/restore`), 'Đã khôi phục tin')}><Icon name="restore" size={14} /> Khôi phục</button>}
              <button className="btn btn-danger btn-sm" onClick={() => confirm('Xóa vĩnh viễn? Không thể hoàn tác.') && act(() => api.del(`/product/${p.product_id}/permanent`), 'Đã xóa vĩnh viễn')}><Icon name="trash" size={14} /> Xóa hẳn</button>
            </div>
          </div>
        )))}

        {!loading && tab === 'bought' && (bought.length === 0 ? (
          <div className="empty-box"><strong>Bạn chưa mua món nào</strong><Link to="/" className="btn btn-primary">Đi dạo một vòng</Link></div>
        ) : bought.map((p) => (
          <div className="mp-row" key={p.product_id}>
            <Thumb src={p.thumbnail_url} />
            <div className="mp-main"><Link to={`/product?id=${p.product_id}`} className="mp-title">{p.title}</Link><div className="mp-meta"><b>{fmtPrice(p.price)}</b><span>Từ {p.seller.full_name}</span><span>{timeAgo(p.purchased_at)}</span></div></div>
            <div className="mp-actions">{p.has_reviewed ? <span className="badge badge-ok">Đã đánh giá</span> : <button className="btn btn-soft btn-sm" onClick={() => setReviewFor(p)}><Icon name="star" size={14} /> Đánh giá người bán</button>}</div>
          </div>
        )))}
      </div>

      {editing && <EditModal p={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); toast('Đã cập nhật tin'); load(tab) }} />}
      {soldFor && <SoldModal p={soldFor} onClose={() => setSoldFor(null)} onDone={() => { setSoldFor(null); toast('Đã đánh dấu đã bán'); load(tab) }} />}
      {reviewFor && <ReviewModal b={reviewFor} onClose={() => setReviewFor(null)} onDone={() => { setReviewFor(null); toast('Cảm ơn bạn đã đánh giá!'); load(tab) }} />}
    </div>
  )
}

function EditModal({ p, onClose, onSaved }: { p: ProductDetail; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState(p.title)
  const [price, setPrice] = useState(String(p.price))
  const [desc, setDesc] = useState(p.description ?? '')
  const [cond, setCond] = useState(String(p.condition_id))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { await api.put(`/product/${p.product_id}/me`, { title: title.trim(), price: Number(price), description: desc, condition_id: Number(cond) }); onSaved() }
    catch (e2) { setErr(errText(e2)) } finally { setBusy(false) }
  }
  return (
    <div className="modal-back" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3>Sửa tin đăng</h3>
        {err && <div className="form-error">{err}</div>}
        <div className="field"><label htmlFor="e-t">Tiêu đề</label><input id="e-t" className="input" required minLength={5} value={title} onChange={(e) => setTitle(e.target.value)} /></div>
        <div className="row">
          <div className="field"><label htmlFor="e-p">Giá (₫)</label><input id="e-p" className="input" type="number" min={0} required value={price} onChange={(e) => setPrice(e.target.value)} /></div>
          <div className="field"><label htmlFor="e-c">Tình trạng</label><select id="e-c" className="select" value={cond} onChange={(e) => setCond(e.target.value)}>{Object.entries(CONDITIONS).map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select></div>
        </div>
        <div className="field"><label htmlFor="e-d">Mô tả</label><textarea id="e-d" className="textarea" value={desc} onChange={(e) => setDesc(e.target.value)} /></div>
        <div className="modal-actions"><button type="button" className="btn btn-ghost" onClick={onClose}>Hủy</button><button className="btn btn-primary" disabled={busy}>{busy ? 'Đang lưu...' : 'Lưu'}</button></div>
      </form>
    </div>
  )
}

function SoldModal({ p, onClose, onDone }: { p: ProductListItem; onClose: () => void; onDone: () => void }) {
  const [buyers, setBuyers] = useState<Buyer[]>([])
  const [buyer, setBuyer] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.get<Buyer[]>(`/interaction/product/${p.product_id}/potential-buyers`).then(setBuyers).catch(() => {}) }, [p.product_id])
  const submit = async () => {
    setBusy(true)
    try { await api.patch(`/product/${p.product_id}/sold`, undefined, { buyer_id: buyer || undefined }); onDone() }
    catch (e) { toast(errText(e), 'err'); setBusy(false) }
  }
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Đã bán “{p.title}”?</h3>
        <div className="field"><label htmlFor="s-b">Người mua (tùy chọn)</label>
          <select id="s-b" className="select" value={buyer} onChange={(e) => setBuyer(e.target.value)}>
            <option value="">Bán ngoài / không chọn</option>{buyers.map((b) => <option key={b.user_id} value={b.user_id}>{b.full_name}</option>)}
          </select>
          <span className="hint">Chọn người đã nhắn tin để họ nhận lời mời đánh giá bạn.</span></div>
        <div className="modal-actions"><button className="btn btn-ghost" onClick={onClose}>Hủy</button><button className="btn btn-primary" onClick={submit} disabled={busy}>Xác nhận đã bán</button></div>
      </div>
    </div>
  )
}

function ReviewModal({ b, onClose, onDone }: { b: Bought; onClose: () => void; onDone: () => void }) {
  const [stars, setStars] = useState(5)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true)
    try { await api.post(`/interaction/product/${b.product_id}/reviews`, { rating: stars, content: text.trim() || null }); onDone() }
    catch (e2) { toast(errText(e2), 'err'); setBusy(false) }
  }
  return (
    <div className="modal-back" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3>Đánh giá {b.seller.full_name}</h3>
        <div className="stars" role="radiogroup" aria-label="Số sao">
          {[1, 2, 3, 4, 5].map((n) => <button type="button" key={n} className={n <= stars ? 'on' : ''} onClick={() => setStars(n)} aria-label={`${n} sao`} role="radio" aria-checked={n === stars}><Icon name="star" size={28} /></button>)}
        </div>
        <div className="field"><label htmlFor="r-t">Nhận xét</label><textarea id="r-t" className="textarea" maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} placeholder="Giao dịch thế nào? Đồ có đúng mô tả không?" /></div>
        <div className="modal-actions"><button type="button" className="btn btn-ghost" onClick={onClose}>Hủy</button><button className="btn btn-primary" disabled={busy}>Gửi đánh giá</button></div>
      </form>
    </div>
  )
}
