import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import ProductCard from '../../components/ui/ProductCard'
import { api, errText, fmtPrice, mediaUrl, Paginated, ProductListItem, timeAgo, toast, useAuth } from '../../lib/api'

interface SellerUser {
  id: number
  Email: string
  account_type?: string | null
  isActive: boolean
  CreatedAt?: string
}

interface FollowStatus {
  user_id: number
  is_following: boolean
  total_followers: number
  total_following: number
}

interface ReviewItem {
  product_id: number
  reviewer: { user_id: number; full_name: string; avatar_url?: string | null }
  rating: number
  content?: string | null
  created_at: string
}

interface SellerReviews {
  seller_id: number
  rating_avg: number
  total_reviews: number
  reviews: ReviewItem[]
}

export default function SellerProfile() {
  const [sp] = useSearchParams()
  const sellerId = Number(sp.get('id'))
  const nav = useNavigate()
  const { loggedIn, userId } = useAuth()

  const [seller, setSeller] = useState<SellerUser | null>(null)
  const [follow, setFollow] = useState<FollowStatus | null>(null)
  const [reviewsData, setReviewsData] = useState<SellerReviews | null>(null)
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [tab, setTab] = useState<'selling' | 'reviews'>('selling')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!sellerId) {
      setErr('Không tìm thấy người bán.')
      setLoading(false)
      return
    }
    setLoading(true)
    setErr('')

    Promise.allSettled([
      api.get<SellerUser>(`/user/${sellerId}`),
      api.get<FollowStatus>(`/interaction/user/${sellerId}/follow-status`),
      api.get<SellerReviews>(`/interaction/user/${sellerId}/reviews`, { page: 1, page_size: 20 }),
      api.get<Paginated<ProductListItem>>('/product', { seller_id: sellerId, page: 1, page_size: 50 }),
    ]).then(([uRes, fRes, rRes, pRes]) => {
      if (uRes.status === 'fulfilled') setSeller(uRes.value)
      else setErr('Người dùng này không tồn tại hoặc đã bị khóa.')

      if (fRes.status === 'fulfilled') setFollow(fRes.value)
      if (rRes.status === 'fulfilled') setReviewsData(rRes.value)
      if (pRes.status === 'fulfilled') setProducts(pRes.value.items)
    }).finally(() => setLoading(false))
  }, [sellerId])

  const toggleFollow = async () => {
    if (!loggedIn) return nav(`/login?next=${encodeURIComponent(`/seller?id=${sellerId}`)}`)
    try {
      const r = await api.post<{ is_following: boolean; message: string }>(`/interaction/user/${sellerId}/follow`)
      setFollow((prev) => prev ? {
        ...prev,
        is_following: r.is_following,
        total_followers: r.is_following ? prev.total_followers + 1 : Math.max(0, prev.total_followers - 1),
      } : null)
      toast(r.message)
    } catch (e) {
      toast(errText(e), 'err')
    }
  }

  if (loading) return <div className="container loading">Đang tải thông tin người bán...</div>
  if (err || !seller) {
    return (
      <div className="container page-empty">
        <h1>Người bán không tồn tại</h1>
        <p>{err || 'Không tìm thấy hồ sơ người bán này.'}</p>
        <Link to="/" className="btn btn-primary">Về trang chủ</Link>
      </div>
    )
  }

  const isMe = userId === seller.id
  const displayName = seller.Email.split('@')[0]

  return (
    <div className="container page">
      <div className="pf-top card" style={{ padding: 24, marginBottom: 24 }}>
        <span className="pf-avatar" style={{ width: 80, height: 80, fontSize: 32 }}>
          {displayName.slice(0, 1).toUpperCase()}
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h1 style={{ margin: 0, fontSize: '1.6rem' }}>{displayName}</h1>
            {seller.account_type === 'Sinh Vien' && <span className="chip chip-soft">Sinh viên đã xác minh</span>}
          </div>
          <div className="hint" style={{ marginTop: 6, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <span>Tham gia từ {seller.CreatedAt ? new Date(seller.CreatedAt).toLocaleDateString('vi-VN') : 'Gần đây'}</span>
            {follow && (
              <>
                <span><b>{follow.total_followers}</b> người theo dõi</span>
                <span>Đang theo dõi <b>{follow.total_following}</b></span>
              </>
            )}
            {reviewsData && reviewsData.total_reviews > 0 ? (
              <span><Icon name="star" size={14} /> <b>{reviewsData.rating_avg}</b> ({reviewsData.total_reviews} đánh giá)</span>
            ) : (
              <span>Chưa có đánh giá</span>
            )}
          </div>
        </div>

        <div className="pf-links">
          {isMe ? (
            <Link to="/profile" className="btn btn-soft"><Icon name="edit" size={16} /> Quản lý hồ sơ của tôi</Link>
          ) : (
            <button className={`btn ${follow?.is_following ? 'btn-ghost' : 'btn-primary'}`} onClick={toggleFollow}>
              {follow?.is_following ? 'Đang theo dõi' : '+ Theo dõi người bán'}
            </button>
          )}
        </div>
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" className={tab === 'selling' ? 'on' : ''} onClick={() => setTab('selling')}>
          Đang bán ({products.length})
        </button>
        <button role="tab" className={tab === 'reviews' ? 'on' : ''} onClick={() => setTab('reviews')}>
          Nhận xét & Đánh giá ({reviewsData?.total_reviews ?? 0})
        </button>
      </div>

      <div style={{ marginTop: 20 }}>
        {tab === 'selling' && (
          products.length === 0 ? (
            <div className="empty-box">
              <strong>Người này chưa có tin đăng nào đang bán</strong>
              <span>Các tin đăng khác có thể đã bán hoặc tạm ẩn.</span>
            </div>
          ) : (
            <div className="grid">
              {products.map((p) => (
                <ProductCard key={p.product_id} p={p} />
              ))}
            </div>
          )
        )}

        {tab === 'reviews' && (
          (!reviewsData || reviewsData.reviews.length === 0) ? (
            <div className="empty-box">
              <strong>Chưa có nhận xét nào</strong>
              <span>Người bán sẽ nhận đánh giá khi giao dịch hoàn tất và được người mua đánh giá.</span>
            </div>
          ) : (
            <div className="card" style={{ display: 'grid', gap: 16 }}>
              {reviewsData.reviews.map((r, i) => (
                <div key={i} style={{ borderBottom: i < reviewsData.reviews.length - 1 ? '1px solid var(--border)' : 'none', paddingBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span className="avatar sm">
                        {r.reviewer.full_name?.slice(0, 1).toUpperCase() || 'U'}
                      </span>
                      <b>{r.reviewer.full_name}</b>
                    </div>
                    <time className="hint">{timeAgo(r.created_at)}</time>
                  </div>
                  <div style={{ color: '#f39c12', margin: '6px 0', display: 'flex', gap: 2 }}>
                    {[1, 2, 3, 4, 5].map((s) => (
                      <Icon key={s} name="star" size={14} className={s <= r.rating ? '' : 'muted'} />
                    ))}
                  </div>
                  {r.content && <p style={{ margin: 0 }}>{r.content}</p>}
                </div>
              ))}
            </div>
          )
        )}
      </div>
    </div>
  )
}
