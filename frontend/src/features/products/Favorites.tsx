import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ProductCard from '../../components/ui/ProductCard'
import { api, errText, Paginated, toast } from '../../lib/api'

interface Fav { product_id: number; title: string; price: number; thumbnail_url?: string | null; condition_name?: string | null; status_id: number; favorited_at: string }

export default function Favorites() {
  const [items, setItems] = useState<Fav[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<Paginated<Fav>>('/interaction/my-favorite', { page: 1, page_size: 100 })
      .then((r) => setItems(r.items)).catch((e) => toast(errText(e), 'err')).finally(() => setLoading(false))
  }, [])

  const unfav = async (id: number) => {
    try {
      await api.post(`/interaction/product/${id}/favorite`)
      setItems((x) => x.filter((i) => i.product_id !== id))
    } catch (e) { toast(errText(e), 'err') }
  }

  return (
    <div className="container page">
      <div className="page-head"><div><h1>Yêu thích</h1><p>Những món bạn đã thả tim.</p></div></div>
      {loading ? <div className="loading">Đang tải...</div> : items.length === 0 ? (
        <div className="empty-box"><strong>Chưa có món yêu thích</strong><span>Bấm vào hình trái tim ở mỗi tin để lưu lại xem sau.</span><Link to="/" className="btn btn-primary">Đi dạo một vòng</Link></div>
      ) : (
        <div className="grid">{items.map((p) => <ProductCard key={p.product_id} p={p} faved onFav={unfav} />)}</div>
      )}
    </div>
  )
}
