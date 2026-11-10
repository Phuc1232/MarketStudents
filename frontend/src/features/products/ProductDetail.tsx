import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, Attribute, CONDITIONS, errText, fmtPrice, mediaUrl, ProductDetail as PD, STATUSES, timeAgo, toast, useAuth } from '../../lib/api'

interface Reply { comment_id: number; content: string; author: { user_id: number; full_name: string }; created_at: string }
interface Comment { comment_id: number; content: string; author: { user_id: number; full_name: string }; created_at: string; replies: Reply[] }

export default function ProductDetail() {
  const [sp] = useSearchParams()
  const id = Number(sp.get('id'))
  const nav = useNavigate()
  const { loggedIn, userId } = useAuth()

  const [p, setP] = useState<PD | null>(null)
  const [attrNames, setAttrNames] = useState<Record<number, string>>({})
  const [err, setErr] = useState('')
  const [img, setImg] = useState(0)
  const [faved, setFaved] = useState(false)
  const [following, setFollowing] = useState(false)
  const [rating, setRating] = useState<{ avg: number; total: number } | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [text, setText] = useState('')
  const [replyTo, setReplyTo] = useState<number | null>(null)

  const loadComments = useCallback(() => {
    api.get<Comment[]>(`/interaction/product/${id}/comments`).then(setComments).catch(() => {})
  }, [id])

  useEffect(() => {
    if (!id) { setErr('Không tìm thấy sản phẩm.'); return }
    setP(null); setErr(''); setImg(0)
    api.get<PD>(`/product/${id}`).then(async (prod) => {
      setP(prod)
      api.get<Attribute[]>(`/masterdata/subcategory/${prod.sub_category_id}/attribute`)
        .then((a) => setAttrNames(Object.fromEntries(a.map((x) => [x.attribute_id, x.name ?? '']))))
        .catch(() => {})
      api.get<{ rating_avg: number; total_reviews: number }>(`/interaction/user/${prod.seller_id}/reviews`, { page_size: 1 })
        .then((r) => setRating({ avg: r.rating_avg, total: r.total_reviews })).catch(() => {})
    }).catch((e) => setErr(errText(e)))
    loadComments()
  }, [id, loadComments])

  useEffect(() => {
    if (!loggedIn || !p) return
    api.post(`/product/${id}/view-history`).catch(() => {})
    api.get<{ is_favorited: boolean }>(`/interaction/${id}/status`).then((r) => setFaved(r.is_favorited)).catch(() => {})
    if (p.seller_id !== userId) api.get<{ is_following: boolean }>(`/interaction/user/${p.seller_id}/follow-status`).then((r) => setFollowing(r.is_following)).catch(() => {})
  }, [loggedIn, p?.product_id]) // eslint-disable-line react-hooks/exhaustive-deps

  const needLogin = () => { nav(`/login?next=${encodeURIComponent(`/product?id=${id}`)}`); return false }

  const toggleFav = async () => {
    if (!loggedIn) return needLogin()
    try { const r = await api.post<{ is_favorited: boolean; message: string }>(`/interaction/product/${id}/favorite`); setFaved(r.is_favorited); toast(r.message) } catch (e) { toast(errText(e), 'err') }
  }
  const toggleFollow = async () => {
    if (!loggedIn || !p) return needLogin()
    try { const r = await api.post<{ is_following: boolean; message: string }>(`/interaction/user/${p.seller_id}/follow`); setFollowing(r.is_following); toast(r.message) } catch (e) { toast(errText(e), 'err') }
  }
  const startChat = async () => {
    if (!loggedIn) return needLogin()
    try {
      const c = await api.post<{ conversation_id: number }>('/interaction/conversations', { product_id: id })
      nav(`/messages?c=${c.conversation_id}`)
    } catch (e) { toast(errText(e), 'err') }
  }
  const postComment = async (e: FormEvent) => {
    e.preventDefault()
    if (!loggedIn) return needLogin()
    if (!text.trim()) return
    try {
      await api.post(`/interaction/product/${id}/comments`, { content: text.trim(), parent_id: replyTo })
      setText(''); setReplyTo(null); loadComments()
    } catch (e2) { toast(errText(e2), 'err') }
  }
  const delComment = async (cid: number) => {
    if (!confirm('Xóa bình luận này?')) return
    try { await api.del(`/interaction/comments/${cid}`); loadComments() } catch (e) { toast(errText(e), 'err') }
  }

  if (err) return <div className="container page-empty"><h1>Ôi, không có gì ở đây</h1><p>{err}</p><Link to="/" className="btn btn-primary">Về trang chủ</Link></div>
  if (!p) return <div className="container loading">Đang tải...</div>

  const images = p.images.length ? [...p.images].sort((a, b) => a.display_order - b.display_order) : []
  const main = mediaUrl(images[img]?.image_url ?? p.thumbnails)
  const mine = userId === p.seller_id
  const status = STATUSES[p.status_id]
  const sellerName = p.seller?.Email?.split('@')[0] ?? `Người bán #${p.seller_id}`

  const renderComment = (c: { comment_id: number; content: string; author: { user_id: number; full_name: string }; created_at: string }, isReply = false) => (
    <div key={c.comment_id} className={`comment${isReply ? ' reply' : ''}`}>
      <span className="avatar">{c.author.full_name.slice(0, 1).toUpperCase()}</span>
      <div>
        <div className="comment-head"><b>{c.author.full_name}</b>{c.author.user_id === p.seller_id && <span className="chip chip-soft">Người bán</span>}<time>{timeAgo(c.created_at)}</time></div>
        <p>{c.content}</p>
        <div className="comment-actions">
          {!isReply && <button onClick={() => { setReplyTo(c.comment_id); document.getElementById('cmt-input')?.focus() }}>Trả lời</button>}
          {(c.author.user_id === userId || mine) && <button onClick={() => delComment(c.comment_id)}>Xóa</button>}
        </div>
      </div>
    </div>
  )

  return (
    <div className="container page">
      <nav className="crumbs"><Link to="/">Trang chủ</Link> / <span>{p.title}</span></nav>

      <div className="pd">
        <div className="pd-gallery">
          <div className="pd-main">{main ? <img src={main} alt={p.title} /> : <span className="pcard-noimg"><Icon name="image" size={48} /></span>}</div>
          {images.length > 1 && (
            <div className="pd-thumbs">
              {images.map((im, i) => <button key={im.image_id} className={i === img ? 'on' : ''} onClick={() => setImg(i)} aria-label={`Ảnh ${i + 1}`}><img src={mediaUrl(im.image_url)} alt="" /></button>)}
            </div>
          )}
        </div>

        <div className="pd-info">
          <div className="pd-badges">
            <span className="chip">{CONDITIONS[p.condition_id] ?? 'Đã dùng'}</span>
            {status && p.status_id !== 2 && <span className={`badge badge-${status.tone}`}>{status.label}</span>}
          </div>
          <h1>{p.title}</h1>
          <div className="pd-price">{fmtPrice(p.price)}</div>
          <div className="pd-stats"><span><Icon name="eye" size={15} /> {p.view_count} lượt xem</span><span>Đăng {timeAgo(p.CreatedAt)}</span></div>

          <div className="pd-actions">
            {mine ? (
              <Link to="/my-products" className="btn btn-soft">Quản lý tin này</Link>
            ) : (
              <button className="btn btn-primary" onClick={startChat} disabled={p.status_id === 3}><Icon name="chat" size={18} /> Nhắn tin cho người bán</button>
            )}
            <button className={`btn btn-ghost fav-btn${faved ? ' on' : ''}`} onClick={toggleFav} aria-pressed={faved}><Icon name="heart" size={18} /> {faved ? 'Đã yêu thích' : 'Yêu thích'}</button>
          </div>

          <div className="pd-seller">
            <span className="avatar lg">{sellerName.slice(0, 1).toUpperCase()}</span>
            <div>
              <b>{sellerName}</b>
              <div className="hint">
                {p.seller?.account_type === 'Sinh Vien' && <span className="chip chip-soft">Sinh viên đã xác minh</span>}{' '}
                {rating && rating.total > 0 ? <span><Icon name="star" size={13} /> {rating.avg} ({rating.total} đánh giá)</span> : 'Chưa có đánh giá'}
              </div>
            </div>
            {!mine && <button className="btn btn-ghost btn-sm" onClick={toggleFollow}>{following ? 'Đang theo dõi' : 'Theo dõi'}</button>}
          </div>

          {p.value.length > 0 && (
            <dl className="pd-attrs">
              {p.value.map((v) => (
                <div key={v.id}><dt>{attrNames[v.attribute_id] || `Thuộc tính ${v.attribute_id}`}</dt><dd>{v.Value_Text || v.Value_Num}</dd></div>
              ))}
            </dl>
          )}
        </div>
      </div>

      <section className="pd-desc card">
        <h2>Mô tả</h2>
        <p>{p.description?.trim() || 'Người bán chưa thêm mô tả.'}</p>
      </section>

      <section className="comments card">
        <h2>Hỏi đáp <small>{comments.length + comments.reduce((n, c) => n + c.replies.length, 0)}</small></h2>
        <form onSubmit={postComment} className="comment-form">
          {replyTo && <div className="hint">Đang trả lời một bình luận · <button type="button" className="link-btn" onClick={() => setReplyTo(null)}>Hủy</button></div>}
          <textarea id="cmt-input" className="textarea" rows={2} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} placeholder={loggedIn ? 'Đặt câu hỏi cho người bán...' : 'Đăng nhập để bình luận'} />
          <button className="btn btn-primary btn-sm">Gửi</button>
        </form>
        {comments.length === 0 ? <p className="hint">Chưa có bình luận nào.</p> : comments.map((c) => (
          <div key={c.comment_id} className="comment-thread">{renderComment(c)}{c.replies.map((r) => renderComment(r, true))}</div>
        ))}
      </section>
    </div>
  )
}
