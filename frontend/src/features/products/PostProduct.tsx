import { ChangeEvent, FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, Attribute, Category, CONDITIONS, District, errText, mediaUrl, Province, toast, Ward } from '../../lib/api'

interface Uploaded { image_url: string }

export default function PostProduct() {
  const nav = useNavigate()
  const [cats, setCats] = useState<Category[]>([])
  const [provinces, setProvinces] = useState<Province[]>([])
  const [districts, setDistricts] = useState<District[]>([])
  const [wards, setWards] = useState<Ward[]>([])
  const [attrs, setAttrs] = useState<Attribute[]>([])
  const [attrVals, setAttrVals] = useState<Record<number, string>>({})
  const [images, setImages] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const [f, setF] = useState({ title: '', price: '', description: '', categoryId: '', subId: '', conditionId: '2', provinceId: '', districtId: '', wardId: '', address: '' })
  const set = (k: keyof typeof f, v: string) => setF((o) => ({ ...o, [k]: v }))

  useEffect(() => {
    api.get<Category[]>('/masterdata/category/sub').then(setCats).catch((e) => toast(errText(e), 'err'))
    api.get<Province[]>('/masterdata/provinces').then(setProvinces).catch(() => {})
  }, [])
  useEffect(() => {
    setAttrs([]); setAttrVals({})
    if (f.subId) api.get<Attribute[]>(`/masterdata/subcategory/${f.subId}/attribute`).then(setAttrs).catch(() => {})
  }, [f.subId])
  useEffect(() => {
    setDistricts([]); setWards([]); setF((o) => ({ ...o, districtId: '', wardId: '' }))
    if (f.provinceId) api.get<District[]>(`/masterdata/provinces/${f.provinceId}/districts`).then(setDistricts).catch(() => {})
  }, [f.provinceId])
  useEffect(() => {
    setWards([]); setF((o) => ({ ...o, wardId: '' }))
    if (f.districtId) api.get<Ward[]>(`/masterdata/districts/${f.districtId}/ward`).then(setWards).catch(() => {})
  }, [f.districtId])

  const pickFiles = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).slice(0, 5 - images.length)
    e.target.value = ''
    if (!files.length) return
    setUploading(true)
    try {
      const fd = new FormData()
      files.forEach((x) => fd.append('files', x))
      const r = await api.upload<{ images: Uploaded[] }>('/upload/images', fd)
      setImages((o) => [...o, ...r.images.map((i) => i.image_url)].slice(0, 5))
    } catch (e2) { toast(errText(e2), 'err') } finally { setUploading(false) }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    if (!images.length) return setErr('Hãy thêm ít nhất 1 ảnh cho món đồ.')
    if (!f.subId) return setErr('Hãy chọn danh mục.')
    setBusy(true)
    try {
      const attributes = attrs.flatMap((a) => {
        const v = (attrVals[a.attribute_id] ?? '').trim()
        if (!v) return []
        return a.data_type === 'number' ? [{ attribute_id: a.attribute_id, value_text: null, value_num: v }] : [{ attribute_id: a.attribute_id, value_text: v, value_num: '' }]
      })
      const created = await api.post<{ product_id: number; status_id: number }>('/product', {
        title: f.title.trim(),
        price: Number(f.price),
        description: f.description.trim() || null,
        thumbnails: images[0],
        sub_category_id: Number(f.subId),
        condition_id: Number(f.conditionId),
        ward_id: f.wardId ? Number(f.wardId) : null,
        specific_address: f.address.trim() || null,
        images: images.map((u, i) => ({ image_url: u, display_order: i, is_thumbnail: i === 0 })),
        attributes,
      })
      toast(created.status_id === 1 ? 'Đã gửi tin, đang chờ duyệt!' : 'Đăng tin thành công!')
      nav(created.status_id === 1 ? '/my-products' : `/product?id=${created.product_id}`)
    } catch (e2) { setErr(errText(e2)) } finally { setBusy(false) }
  }

  const subs = cats.find((c) => String(c.category_id) === f.categoryId)?.subcategories ?? []

  return (
    <div className="container-narrow page">
      <div className="page-head"><div><h1>Đăng tin mới</h1><p>Điền thật rõ ràng để món đồ tìm được chủ mới nhanh hơn.</p></div></div>
      <form className="card post-form" onSubmit={submit}>
        {err && <div className="form-error" role="alert">{err}</div>}

        <div className="field">
          <span className="label">Hình ảnh ({images.length}/5)</span>
          <div className="img-grid">
            {images.map((u, i) => (
              <div key={u} className="img-tile">
                <img src={mediaUrl(u)} alt={`Ảnh ${i + 1}`} />
                {i === 0 && <span className="img-cover">Ảnh bìa</span>}
                <button type="button" onClick={() => setImages((o) => o.filter((x) => x !== u))} aria-label="Xóa ảnh"><Icon name="x" size={14} /></button>
              </div>
            ))}
            {images.length < 5 && (
              <label className="img-add">
                <Icon name="plus" size={22} /><span>{uploading ? 'Đang tải...' : 'Thêm ảnh'}</span>
                <input type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={pickFiles} disabled={uploading} />
              </label>
            )}
          </div>
          <span className="hint">JPG, PNG hoặc WebP, tối đa 10MB mỗi ảnh. Ảnh đầu tiên là ảnh bìa.</span>
        </div>

        <div className="field"><label htmlFor="p-title">Tiêu đề</label><input id="p-title" className="input" required minLength={5} maxLength={255} value={f.title} onChange={(e) => set('title', e.target.value)} placeholder="VD: Giáo trình Giải tích 1 còn mới 95%" /></div>

        <div className="row">
          <div className="field"><label htmlFor="p-cat">Danh mục</label>
            <select id="p-cat" className="select" required value={f.categoryId} onChange={(e) => { set('categoryId', e.target.value); set('subId', '') }}>
              <option value="">Chọn danh mục</option>{cats.map((c) => <option key={c.category_id} value={c.category_id}>{c.name}</option>)}
            </select></div>
          <div className="field"><label htmlFor="p-sub">Danh mục con</label>
            <select id="p-sub" className="select" required value={f.subId} onChange={(e) => set('subId', e.target.value)} disabled={!subs.length}>
              <option value="">Chọn danh mục con</option>{subs.map((s) => <option key={s.sub_category_id} value={s.sub_category_id}>{s.name}</option>)}
            </select></div>
        </div>

        <div className="row">
          <div className="field"><label htmlFor="p-price">Giá bán (₫)</label><input id="p-price" className="input" type="number" min={0} step={1000} required value={f.price} onChange={(e) => set('price', e.target.value)} placeholder="0" /></div>
          <div className="field"><label htmlFor="p-cond">Tình trạng</label>
            <select id="p-cond" className="select" value={f.conditionId} onChange={(e) => set('conditionId', e.target.value)}>{Object.entries(CONDITIONS).map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select></div>
        </div>

        {attrs.length > 0 && (
          <div className="attr-box">
            <span className="label">Thông số</span>
            <div className="row">
              {attrs.map((a) => (
                <div className="field" key={a.attribute_id}>
                  <label htmlFor={`a-${a.attribute_id}`}>{a.name}</label>
                  {a.option?.length ? (
                    <select id={`a-${a.attribute_id}`} className="select" value={attrVals[a.attribute_id] ?? ''} onChange={(e) => setAttrVals((o) => ({ ...o, [a.attribute_id]: e.target.value }))}>
                      <option value="">Chọn</option>{a.option.map((o) => <option key={o.option_id} value={o.option_value}>{o.option_value}</option>)}
                    </select>
                  ) : (
                    <input id={`a-${a.attribute_id}`} className="input" type={a.data_type === 'number' ? 'number' : 'text'} value={attrVals[a.attribute_id] ?? ''} onChange={(e) => setAttrVals((o) => ({ ...o, [a.attribute_id]: e.target.value }))} />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="field"><label htmlFor="p-desc">Mô tả</label><textarea id="p-desc" className="textarea" value={f.description} onChange={(e) => set('description', e.target.value)} placeholder="Nêu rõ tình trạng, lý do bán, phụ kiện đi kèm..." /></div>

        <div className="field">
          <span className="label">Nơi giao dịch (không bắt buộc)</span>
          <div className="row-3 row">
            <select className="select" value={f.provinceId} onChange={(e) => set('provinceId', e.target.value)} aria-label="Tỉnh / Thành phố"><option value="">Tỉnh / Thành</option>{provinces.map((x) => <option key={x.province_id} value={x.province_id}>{x.province_name}</option>)}</select>
            <select className="select" value={f.districtId} onChange={(e) => set('districtId', e.target.value)} disabled={!districts.length} aria-label="Quận / Huyện"><option value="">Quận / Huyện</option>{districts.map((x) => <option key={x.district_id} value={x.district_id}>{x.district_name}</option>)}</select>
            <select className="select" value={f.wardId} onChange={(e) => set('wardId', e.target.value)} disabled={!wards.length} aria-label="Phường / Xã"><option value="">Phường / Xã</option>{wards.map((x) => <option key={x.ward_id} value={x.ward_id}>{x.ward_name}</option>)}</select>
          </div>
          <input className="input" value={f.address} onChange={(e) => set('address', e.target.value)} placeholder="Địa chỉ cụ thể (VD: KTX Khu B, cổng trường)" />
        </div>

        <button className="btn btn-primary" disabled={busy || uploading}>{busy ? 'Đang đăng...' : 'Đăng tin'}</button>
      </form>
    </div>
  )
}
