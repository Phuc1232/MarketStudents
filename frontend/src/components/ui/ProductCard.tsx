import { Link } from 'react-router-dom'
import Icon from './Icon'
import { CONDITIONS, fmtPrice, mediaUrl, timeAgo } from '../../lib/api'

export interface CardProduct {
  product_id: number
  title: string
  price: number
  thumbnails?: string | null
  thumbnail_url?: string | null
  condition_id?: number
  condition_name?: string | null
  CreatedAt?: string | null
  status_id?: number
}

export default function ProductCard({ p, faved, onFav }: { p: CardProduct; faved?: boolean; onFav?: (id: number) => void }) {
  const img = mediaUrl(p.thumbnails ?? p.thumbnail_url)
  const cond = p.condition_name ?? (p.condition_id ? CONDITIONS[p.condition_id] : '')
  return (
    <article className="pcard">
      <Link to={`/product?id=${p.product_id}`} className="pcard-img">
        {img ? <img src={img} alt={p.title} loading="lazy" /> : <span className="pcard-noimg"><Icon name="image" size={30} /></span>}
        {p.status_id === 3 && <span className="pcard-sold">Đã bán</span>}
      </Link>
      {onFav && (
        <button className={`pcard-fav${faved ? ' on' : ''}`} onClick={() => onFav(p.product_id)} aria-label={faved ? 'Bỏ yêu thích' : 'Yêu thích'} aria-pressed={!!faved}>
          <Icon name="heart" size={18} />
        </button>
      )}
      <div className="pcard-body">
        <Link to={`/product?id=${p.product_id}`} className="pcard-title">{p.title}</Link>
        <div className="pcard-price">{fmtPrice(p.price)}</div>
        <div className="pcard-meta">
          {cond && <span className="chip chip-soft">{cond}</span>}
          {p.CreatedAt && <span className="pcard-time">{timeAgo(p.CreatedAt)}</span>}
        </div>
      </div>
    </article>
  )
}
