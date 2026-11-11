import { FormEvent, useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import ProductCard from '../../components/ui/ProductCard'
import { api, Category, CONDITIONS, District, errText, Paginated, ProductListItem, Province, toast, useAuth } from '../../lib/api'

const PAGE_SIZE = 12
const FALLBACK_TRENDING = ['giáo trình', 'máy tính', 'đèn học']

interface SavedSearch { search_id: number; keyword: string }

function Hero({ onSearch, trending, history, onDeleteHistory }: { onSearch: (q: string) => void; trending: string[]; history?: SavedSearch[]; onDeleteHistory?: (id: number) => void }) {
  const [q, setQ] = useState('')
  const submit = (e: FormEvent) => { e.preventDefault(); onSearch(q.trim()) }
  return (
    <section className="hero">
      <div className="hero-copy">
        <span className="hero-eyebrow"><i className="hero-dot" /> CHỢ RIÊNG CỦA TỤI MÌNH</span>
        <h1>Đồ tốt có chủ mới.<br /><span>Ví tiền có niềm vui.</span></h1>
        <p>Mua bán đồ dùng sinh viên thật dễ. Tiết kiệm một chút, sống xanh thêm nhiều.</p>
        <form className="hero-search" onSubmit={submit} role="search">
          <Icon name="search" size={20} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Bạn đang cần tìm gì?" aria-label="Bạn đang cần tìm gì?" />
          <button type="submit">Tìm ngay <Icon name="arrow" size={16} strokeWidth={2.2} /></button>
        </form>
        <div className="hero-trending">
          <span>Đang được tìm:</span>
          {trending.slice(0, 3).map((t) => <button key={t} type="button" onClick={() => onSearch(t)}>{t}</button>)}
        </div>
        {history && history.length > 0 && (
          <div className="hero-trending" style={{ marginTop: 8 }}>
            <span>Đã tìm gần đây:</span>
            {history.slice(0, 4).map((h) => (
              <span key={h.search_id} className="chip chip-btn" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '2px 8px' }}>
                <span onClick={() => onSearch(h.keyword)} style={{ cursor: 'pointer' }}>{h.keyword}</span>
                {onDeleteHistory && (
                  <button type="button" onClick={() => onDeleteHistory(h.search_id)} aria-label="Xóa" style={{ border: 'none', background: 'transparent', cursor: 'pointer', display: 'inline-flex', padding: 0 }}>
                    <Icon name="x" size={12} />
                  </button>
                )}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="hero-art" aria-hidden="true">
        <svg className="hero-spark" width="26" height="26" viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"><path d="M13 2v22M2 13h22M5 5l16 16M21 5 5 21" /></svg>
        <div className="art-circle c1"><div className="art-circle c2"><div className="art-circle c3">
          <p className="art-text"><span>reuse</span><b>your</b><span>joy</span></p>
        </div></div></div>
        <div className="art-card art-book"><Icon name="book" size={36} strokeWidth={1.6} /><p>chuyện cũ<br />mở trang mới</p></div>
        <div className="art-card art-laptop"><Icon name="laptop" size={38} strokeWidth={1.6} /></div>
        <div className="art-note">Món xịn<br />giá sinh viên <svg width="16" height="16" viewBox="0 0 24 24" fill="#e9915e"><path d="M12 2l1.9 6.1L20 10l-6.1 1.9L12 18l-1.9-6.1L4 10l6.1-1.9zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" /></svg></div>
      </div>
    </section>
  )
}

export default function Home() {
  const nav = useNavigate()
  const { loggedIn } = useAuth()
  const [sp, setSp] = useSearchParams()
  const [cats, setCats] = useState<Category[]>([])
  const [provinces, setProvinces] = useState<Province[]>([])
  const [districts, setDistricts] = useState<District[]>([])
  const [history, setHistory] = useState<SavedSearch[]>([])
  const [trending, setTrending] = useState<string[]>(FALLBACK_TRENDING)
  const [items, setItems] = useState<ProductListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [favs, setFavs] = useState<Set<number>>(new Set())

  const keyword = sp.get('keyword') ?? ''
  const categoryId = sp.get('category_id') ?? ''
  const subId = sp.get('sub_category_id') ?? ''
  const sort = sp.get('sort_by') ?? 'newest'
  const cond = sp.get('condition_id') ?? ''
  const minP = sp.get('min_price') ?? ''
  const maxP = sp.get('max_price') ?? ''
  const provinceId = sp.get('province_id') ?? ''
  const districtId = sp.get('district_id') ?? ''

  const setParam = (patch: Record<string, string>) => {
    const n = new URLSearchParams(sp)
    Object.entries(patch).forEach(([k, v]) => (v ? n.set(k, v) : n.delete(k)))
    setSp(n, { replace: false })
  }

  useEffect(() => {
    api.get<Category[]>('/masterdata/category/sub').then(setCats).catch(() => {})
    api.get<string[]>('/product/search/suggestions').then((s) => s?.length && setTrending(s)).catch(() => {})
    api.get<Province[]>('/masterdata/provinces').then(setProvinces).catch(() => {})
  }, [])

  useEffect(() => {
    setDistricts([])
    if (provinceId) {
      api.get<District[]>(`/masterdata/provinces/${provinceId}/districts`).then(setDistricts).catch(() => {})
    }
  }, [provinceId])

  useEffect(() => {
    if (!loggedIn) { setFavs(new Set()); setHistory([]); return }
    api.get<Paginated<{ product_id: number }>>('/interaction/my-favorite', { page: 1, page_size: 100 })
      .then((r) => setFavs(new Set(r.items.map((i) => i.product_id)))).catch(() => {})
    api.get<SavedSearch[]>('/user/search-history').then(setHistory).catch(() => {})
  }, [loggedIn])

  const deleteHistory = async (id: number) => {
    try {
      await api.del(`/user/search-history/${id}`)
      setHistory((prev) => prev.filter((h) => h.search_id !== id))
    } catch { /* bỏ qua */ }
  }

  const load = useCallback(async (p: number, replace: boolean) => {
    setLoading(true)
    try {
      const r = await api.get<Paginated<ProductListItem>>('/product', {
        keyword, category_id: categoryId, sub_category_id: subId, sort_by: sort,
        condition_id: cond, min_price: minP, max_price: maxP,
        province_id: provinceId || undefined, district_id: districtId || undefined,
        page: p, page_size: PAGE_SIZE,
      })
      setItems((old) => (replace ? r.items : [...old, ...r.items]))
      setTotal(r.total); setPage(p)
    } catch (e) { toast(errText(e), 'err') } finally { setLoading(false) }
  }, [keyword, categoryId, subId, sort, cond, minP, maxP, provinceId, districtId])

  useEffect(() => { load(1, true) }, [load])

  // Cuộn tới danh sách khi có #products
  useEffect(() => { if (location.hash === '#products') setTimeout(() => document.getElementById('products')?.scrollIntoView({ behavior: 'smooth' }), 80) }, [keyword])

  const search = (q: string) => {
    setParam({ keyword: q })
    if (q && loggedIn) {
      api.post<SavedSearch>('/user/search-history', { keyword: q })
        .then((created) => setHistory((prev) => [created, ...prev.filter((h) => h.keyword !== q)].slice(0, 10)))
        .catch(() => {})
    }
    setTimeout(() => document.getElementById('products')?.scrollIntoView({ behavior: 'smooth' }), 60)
  }

  const toggleFav = async (id: number) => {
    if (!loggedIn) return nav('/login?next=/')
    try {
      const r = await api.post<{ is_favorited: boolean }>(`/interaction/product/${id}/favorite`)
      setFavs((s) => { const n = new Set(s); r.is_favorited ? n.add(id) : n.delete(id); return n })
    } catch (e) { toast(errText(e), 'err') }
  }

  const activeCat = cats.find((c) => String(c.category_id) === categoryId)
  const hasFilter = !!(keyword || categoryId || subId || cond || minP || maxP || provinceId || districtId)

  return (
    <>
      <div className="container"><Hero onSearch={search} trending={trending} history={history} onDeleteHistory={deleteHistory} /></div>

      <section className="container browse">
        <div className="section-head">
          <div><span className="eyebrow">LƯỚT MỘT VÒNG</span><h2>Mua gì hôm nay?</h2></div>
          <span className="section-note">Mỗi món đồ, một hành trình mới <Icon name="arrowup" size={14} /></span>
        </div>
        <div className="cat-row">
          <button className={`cat-tile${!categoryId ? ' on' : ''}`} onClick={() => setParam({ category_id: '', sub_category_id: '' })}>
            <span className="cat-ico"><Icon name="tag" size={20} /></span>Tất cả
          </button>
          {cats.map((c) => (
            <button key={c.category_id} className={`cat-tile${String(c.category_id) === categoryId ? ' on' : ''}`} onClick={() => setParam({ category_id: String(c.category_id), sub_category_id: '' })}>
              <span className="cat-ico">{c.icon_url ? <img src={c.icon_url} alt="" /> : <Icon name="tag" size={20} />}</span>
              {c.name}
            </button>
          ))}
        </div>
        {activeCat && (
          <div className="sub-row">
            {activeCat.subcategories.map((s) => (
              <button key={s.sub_category_id} className={`chip chip-btn${String(s.sub_category_id) === subId ? ' on' : ''}`} onClick={() => setParam({ sub_category_id: String(s.sub_category_id) === subId ? '' : String(s.sub_category_id) })}>{s.name}</button>
            ))}
          </div>
        )}
      </section>

      <section className="container" id="products">
        <div className="list-head">
          <h2>{keyword ? <>Kết quả cho “{keyword}”</> : 'Mới đăng gần đây'} <small>{total} tin</small></h2>
          <div className="filters">
            <select className="select" value={sort} onChange={(e) => setParam({ sort_by: e.target.value === 'newest' ? '' : e.target.value })} aria-label="Sắp xếp">
              <option value="newest">Mới nhất</option>
              <option value="price_asc">Giá thấp → cao</option>
              <option value="price_desc">Giá cao → thấp</option>
              <option value="popular">Xem nhiều nhất</option>
            </select>
            <select className="select" value={provinceId} onChange={(e) => setParam({ province_id: e.target.value, district_id: '' })} aria-label="Tỉnh / Thành phố">
              <option value="">Tất cả Tỉnh/Thành</option>
              {provinces.map((p) => <option key={p.province_id} value={p.province_id}>{p.province_name}</option>)}
            </select>
            {districts.length > 0 && (
              <select className="select" value={districtId} onChange={(e) => setParam({ district_id: e.target.value })} aria-label="Quận / Huyện">
                <option value="">Tất cả Quận/Huyện</option>
                {districts.map((d) => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
              </select>
            )}
            <select className="select" value={cond} onChange={(e) => setParam({ condition_id: e.target.value })} aria-label="Tình trạng">
              <option value="">Mọi tình trạng</option>
              {Object.entries(CONDITIONS).map(([id, n]) => <option key={id} value={id}>{n}</option>)}
            </select>
            <input className="input price-in" type="number" min={0} placeholder="Giá từ" defaultValue={minP} key={`min${minP}`} onBlur={(e) => e.target.value !== minP && setParam({ min_price: e.target.value })} aria-label="Giá thấp nhất" />
            <input className="input price-in" type="number" min={0} placeholder="Đến" defaultValue={maxP} key={`max${maxP}`} onBlur={(e) => e.target.value !== maxP && setParam({ max_price: e.target.value })} aria-label="Giá cao nhất" />
            {hasFilter && <button className="btn btn-ghost btn-sm" onClick={() => setSp({})}>Xóa lọc</button>}
          </div>
        </div>

        {items.length === 0 && !loading ? (
          <div className="empty-box"><strong>Chưa có món nào phù hợp</strong><span>Thử đổi từ khóa hoặc bỏ bớt bộ lọc nhé.</span></div>
        ) : (
          <div className="grid">
            {items.map((p) => <ProductCard key={p.product_id} p={p} faved={favs.has(p.product_id)} onFav={toggleFav} />)}
          </div>
        )}
        {loading && <div className="loading">Đang tải...</div>}
        {!loading && items.length < total && (
          <div className="more"><button className="btn btn-ghost" onClick={() => load(page + 1, false)}>Xem thêm</button></div>
        )}
      </section>
    </>
  )
}
