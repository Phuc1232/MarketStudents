import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../../components/ui/Icon'
import { api, errText, fmtPrice, getUserAccountType, getUserRole, mediaUrl, Paginated, timeAgo, toast, useAuth } from '../../lib/api'

type AdminTab = 'stats' | 'products' | 'reports' | 'verifications'

interface DashboardStats {
  total_users: number
  active_users: number
  banned_users: number
  verified_students: number
  total_products: number
  pending_products: number
  active_products: number
  sold_products: number
  rejected_products: number
  pending_reports: number
  resolved_reports: number
  pending_appeals: number
}

interface PendingProduct {
  product_id: number
  title: string
  price: number
  thumbnail_url?: string | null
  category_name: string
  subcategory_name: string
  condition_name?: string | null
  seller: { user_id: number; email: string; account_type?: string | null }
  status_id: number
  status_name: string
  created_at: string
}

interface AdminReport {
  report_id: number
  reporter_id: number
  reporter_name: string
  reporter_avatar?: string | null
  reason_id: number
  reason_content: string
  target_type: string
  target_id: number
  status: string
  created_at: string
}

interface AppealRequest {
  request_id: number
  user_id: number
  user_email: string
  user_name: string
  contact_phone: string
  other_phone?: string | null
  cccd_front_url: string
  cccd_back_url: string
  sim_ownership_url: string
  status: string
  note?: string | null
  submit_at: string
}

export default function AdminPortal() {
  const { loggedIn, logout } = useAuth()
  const nav = useNavigate()
  const [tab, setTab] = useState<AdminTab>('stats')
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null)
  const [userRole, setUserRole] = useState<number | null>(null)
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [pendingProds, setPendingProds] = useState<PendingProduct[]>([])
  const [reports, setReports] = useState<AdminReport[]>([])
  const [appeals, setAppeals] = useState<AppealRequest[]>([])
  const [loading, setLoading] = useState(true)

  // Modals state
  const [rejectProd, setRejectProd] = useState<PendingProduct | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [resolveRep, setResolveRep] = useState<AdminReport | null>(null)
  const [resolveAction, setResolveAction] = useState('')
  const [banUserChecked, setBanUserChecked] = useState(false)
  const [delTargetChecked, setDelTargetChecked] = useState(true)
  const [dismissRep, setDismissRep] = useState<AdminReport | null>(null)
  const [dismissReason, setDismissReason] = useState('')
  const [busy, setBusy] = useState(false)

  // Kiểm tra quyền Admin/Staff
  useEffect(() => {
    if (!loggedIn) {
      setIsAdmin(false)
      setLoading(false)
      return
    }
    const role = getUserRole()
    const accType = getUserAccountType()
    if (role === 1 || role === 4 || accType === 'Admin' || accType === 'Staff') {
      setUserRole(role ?? 1)
      setIsAdmin(true)
    }

    api.get<{ role_id?: number; account_type?: string }>('/user/me')
      .then((res) => {
        const r = res.role_id ?? role ?? 3
        const isAdm = r === 1 || r === 4 || res.account_type === 'Admin' || res.account_type === 'Staff'
        setUserRole(r)
        setIsAdmin(isAdm)
      })
      .catch(() => {
        if (!isAdmin) setIsAdmin(false)
      })
      .finally(() => setLoading(false))
  }, [loggedIn])

  const loadTabData = async (t: AdminTab) => {
    setLoading(true)
    try {
      if (t === 'stats') {
        const s = await api.get<DashboardStats>('/admin/dashboard/stats')
        setStats(s)
      } else if (t === 'products') {
        const res = await api.get<{ items: PendingProduct[] }>('/admin/products/pending', { page: 1, page_size: 50 })
        setPendingProds(res.items)
      } else if (t === 'reports') {
        const res = await api.get<{ items: AdminReport[] }>('/admin/reports', { page: 1, page_size: 50 })
        setReports(res.items)
      } else if (t === 'verifications') {
        const res = await api.get<{ items: AppealRequest[] }>('/admin/identity-verifications', { page: 1, page_size: 50 })
        setAppeals(res.items)
      }
    } catch (e) {
      toast(errText(e), 'err')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isAdmin) loadTabData(tab)
  }, [isAdmin, tab])

  if (loading && isAdmin === null) return <div className="container loading">Đang kiểm tra quyền truy cập...</div>

  if (!isAdmin) {
    return (
      <div className="container page-empty" style={{ maxWidth: 500, margin: '80px auto', textAlign: 'center' }}>
        <Icon name="shield" size={48} className="muted" />
        <h1 style={{ marginTop: 16 }}>Quyền truy cập bị từ chối</h1>
        <p>Khu vực này chỉ dành riêng cho Ban Quản Trị và Nhân viên Kiểm duyệt (Staff).</p>
        <div style={{ marginTop: 20 }}>
          <Link to="/" className="btn btn-primary">Về trang chủ</Link>
        </div>
      </div>
    )
  }

  // --- ACTIONS CHO SẢN PHẨM ---
  const handleApproveProd = async (id: number) => {
    try {
      await api.patch(`/admin/products/${id}/approve`)
      toast('Đã phê duyệt tin đăng sang trạng thái Hoạt động (Active)!')
      setPendingProds((prev) => prev.filter((p) => p.product_id !== id))
    } catch (e) {
      toast(errText(e), 'err')
    }
  }

  const handleRejectProdSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!rejectProd || rejectReason.trim().length < 10) {
      return toast('Lý do từ chối cần tối thiểu 10 ký tự', 'err')
    }
    setBusy(true)
    try {
      await api.patch(`/admin/products/${rejectProd.product_id}/reject`, { reject_reason: rejectReason.trim() })
      toast('Đã từ chối tin đăng thành công!')
      setPendingProds((prev) => prev.filter((p) => p.product_id !== rejectProd.product_id))
      setRejectProd(null)
      setRejectReason('')
    } catch (e2) {
      toast(errText(e2), 'err')
    } finally {
      setBusy(false)
    }
  }

  // --- ACTIONS CHO BÁO CÁO VI PHẠM ---
  const handleResolveReportSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!resolveRep || resolveAction.trim().length < 5) {
      return toast('Vui lòng mô tả biện pháp xử lý (tối thiểu 5 ký tự)', 'err')
    }
    setBusy(true)
    try {
      await api.post(`/admin/reports/${resolveRep.report_id}/resolve`, {
        action_taken: resolveAction.trim(),
        ban_user: banUserChecked,
        delete_target: delTargetChecked,
        add_blacklist: false,
      })
      toast('Đã giải quyết tố cáo thành công!')
      setReports((prev) => prev.map((r) => r.report_id === resolveRep.report_id ? { ...r, status: 'Resolved' } : r))
      setResolveRep(null)
      setResolveAction('')
    } catch (e2) {
      toast(errText(e2), 'err')
    } finally {
      setBusy(false)
    }
  }

  const handleDismissReportSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!dismissRep || dismissReason.trim().length < 10) {
      return toast('Lý do bác bỏ cần tối thiểu 10 ký tự', 'err')
    }
    setBusy(true)
    try {
      await api.post(`/admin/reports/${dismissRep.report_id}/dismiss`, { dismiss_reason: dismissReason.trim() })
      toast('Đã bác bỏ tố cáo!')
      setReports((prev) => prev.map((r) => r.report_id === dismissRep.report_id ? { ...r, status: 'Dismissed' } : r))
      setDismissRep(null)
      setDismissReason('')
    } catch (e2) {
      toast(errText(e2), 'err')
    } finally {
      setBusy(false)
    }
  }

  // --- ACTIONS CHO KHÁNG CÁO CCCD ---
  const handleApproveAppeal = async (reqId: number) => {
    try {
      await api.patch(`/admin/identity-verifications/${reqId}/approve`)
      toast('Đã phê duyệt kháng cáo & mở khóa tài khoản thành công!')
      setAppeals((prev) => prev.map((a) => a.request_id === reqId ? { ...a, status: 'APPROVED' } : a))
    } catch (e) {
      toast(errText(e), 'err')
    }
  }

  const handleRejectAppeal = async (reqId: number) => {
    const reason = prompt('Nhập lý do từ chối kháng cáo:')
    if (!reason || reason.trim().length < 5) return
    try {
      await api.patch(`/admin/identity-verifications/${reqId}/reject`, { reject_reason: reason.trim() })
      toast('Đã từ chối đơn kháng cáo!')
      setAppeals((prev) => prev.map((a) => a.request_id === reqId ? { ...a, status: 'REJECTED' } : a))
    } catch (e) {
      toast(errText(e), 'err')
    }
  }

  return (
    <div className="container page admin-page">
      <div className="page-head" style={{ marginBottom: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1>Bảng Điều Khiển Quản Trị</h1>
            <span className="badge badge-ok">{userRole === 1 ? 'Super Admin' : 'Staff Moderation'}</span>
          </div>
          <p className="hint">Kiểm duyệt tin đăng, giải quyết vi phạm và giám sát chỉ số sàn UniMarket.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Link to="/" className="btn btn-ghost"><Icon name="back" size={16} /> Về sàn mua bán</Link>
          <button className="btn btn-ghost" onClick={() => { logout(); nav('/login') }}><Icon name="logout" size={16} /> Đăng xuất</button>
        </div>
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" className={tab === 'stats' ? 'on' : ''} onClick={() => setTab('stats')}>
          Thống kê sàn
        </button>
        <button role="tab" className={tab === 'products' ? 'on' : ''} onClick={() => setTab('products')}>
          Duyệt tin đăng {pendingProds.length > 0 && <span className="nav-badge" style={{ position: 'static', marginLeft: 6 }}>{pendingProds.length}</span>}
        </button>
        <button role="tab" className={tab === 'reports' ? 'on' : ''} onClick={() => setTab('reports')}>
          Báo cáo vi phạm
        </button>
        <button role="tab" className={tab === 'verifications' ? 'on' : ''} onClick={() => setTab('verifications')}>
          Kháng cáo CCCD / SIM
        </button>
      </div>

      <div style={{ marginTop: 24 }}>
        {loading && <div className="loading">Đang tải dữ liệu...</div>}

        {/* TAB 1: THỐNG KÊ DASHBOARD */}
        {!loading && tab === 'stats' && stats && (
          <div className="admin-stats-grid">
            <div className="card" style={{ padding: 18 }}>
              <div className="hint">Tổng người dùng</div>
              <div style={{ fontSize: '2rem', fontWeight: 700, margin: '6px 0' }}>{stats.total_users}</div>
              <div className="hint" style={{ fontSize: '0.85rem' }}>Đang hoạt động: {stats.active_users} · Bị khóa: {stats.banned_users}</div>
            </div>

            <div className="card" style={{ padding: 18 }}>
              <div className="hint">Sinh viên đã xác minh</div>
              <div style={{ fontSize: '2rem', fontWeight: 700, margin: '6px 0', color: '#27ae60' }}>{stats.verified_students}</div>
              <div className="hint" style={{ fontSize: '0.85rem' }}>Huy hiệu sinh viên uy tín</div>
            </div>

            <div className="card" style={{ padding: 18 }}>
              <div className="hint">Tin đăng chờ duyệt</div>
              <div style={{ fontSize: '2rem', fontWeight: 700, margin: '6px 0', color: stats.pending_products > 0 ? '#e67e22' : 'inherit' }}>
                {stats.pending_products}
              </div>
              <div className="hint" style={{ fontSize: '0.85rem' }}>Đang bán: {stats.active_products} · Đã bán: {stats.sold_products}</div>
            </div>

            <div className="card" style={{ padding: 18 }}>
              <div className="hint">Báo cáo chờ xử lý</div>
              <div style={{ fontSize: '2rem', fontWeight: 700, margin: '6px 0', color: stats.pending_reports > 0 ? '#e74c3c' : 'inherit' }}>
                {stats.pending_reports}
              </div>
              <div className="hint" style={{ fontSize: '0.85rem' }}>Đã giải quyết: {stats.resolved_reports} · Kháng cáo: {stats.pending_appeals}</div>
            </div>
          </div>
        )}

        {/* TAB 2: DUYỆT TIN ĐĂNG */}
        {!loading && tab === 'products' && (
          pendingProds.length === 0 ? (
            <div className="empty-box">
              <strong>Không có tin đăng nào đang chờ duyệt</strong>
              <span>Tất cả tin đăng đều đã được xử lý.</span>
            </div>
          ) : (
            <div className="mp-list">
              {pendingProds.map((p) => (
                <div key={p.product_id} className="mp-row" style={{ alignItems: 'flex-start' }}>
                  <span className="row-thumb" style={{ width: 80, height: 80 }}>
                    {p.thumbnail_url ? <img src={mediaUrl(p.thumbnail_url)} alt="" /> : <Icon name="image" size={24} />}
                  </span>
                  <div className="mp-main">
                    <Link to={`/product?id=${p.product_id}`} target="_blank" className="mp-title" style={{ fontSize: '1.1rem' }}>
                      {p.title} <Icon name="arrowup" size={12} />
                    </Link>
                    <div className="mp-meta" style={{ margin: '6px 0' }}>
                      <b style={{ color: 'var(--primary, #e67e22)', fontSize: '1rem' }}>{fmtPrice(p.price)}</b>
                      <span className="chip">{p.category_name} / {p.subcategory_name}</span>
                      {p.condition_name && <span>{p.condition_name}</span>}
                      <span>Gửi {timeAgo(p.created_at)}</span>
                    </div>
                    <div className="hint">
                      Người bán: <b>{p.seller.email}</b> {p.seller.account_type === 'Sinh Vien' && <span className="chip chip-soft">Sinh viên</span>}
                    </div>
                  </div>
                  <div className="mp-actions" style={{ flexDirection: 'column', gap: 8 }}>
                    <button className="btn btn-primary btn-sm" onClick={() => handleApproveProd(p.product_id)}>
                      <Icon name="check" size={14} /> Phê duyệt
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => { setRejectProd(p); setRejectReason('') }}>
                      <Icon name="x" size={14} /> Từ chối
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {/* TAB 3: BÁO CÁO VI PHẠM */}
        {!loading && tab === 'reports' && (
          reports.length === 0 ? (
            <div className="empty-box">
              <strong>Chưa có báo cáo vi phạm nào</strong>
              <span>Cộng đồng mua bán đang rất văn minh.</span>
            </div>
          ) : (
            <div className="mp-list">
              {reports.map((r) => (
                <div key={r.report_id} className="mp-row" style={{ alignItems: 'flex-start' }}>
                  <div className="mp-main">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span className="badge badge-warn">Tố cáo #{r.report_id}</span>
                      <b>Đối tượng: {r.target_type} #{r.target_id}</b>
                    </div>
                    <div style={{ margin: '6px 0', fontSize: '0.95rem' }}>
                      Lý do: <b style={{ color: '#c0392b' }}>{r.reason_content}</b>
                    </div>
                    <div className="hint">
                      Người báo cáo: {r.reporter_name} (ID: #{r.reporter_id}) · {timeAgo(r.created_at)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className={`badge badge-${r.status === 'Pending' ? 'warn' : r.status === 'Resolved' ? 'ok' : 'muted'}`}>
                      {r.status === 'Pending' ? 'Chờ xử lý' : r.status === 'Resolved' ? 'Đã giải quyết' : 'Đã bác bỏ'}
                    </span>
                    {r.status === 'Pending' && (
                      <div className="mp-actions">
                        <button className="btn btn-danger btn-sm" onClick={() => { setResolveRep(r); setResolveAction('') }}>
                          Xử lý
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => { setDismissRep(r); setDismissReason('') }}>
                          Bác bỏ
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {/* TAB 4: KHÁNG CÁO CCCD */}
        {!loading && tab === 'verifications' && (
          appeals.length === 0 ? (
            <div className="empty-box">
              <strong>Không có hồ sơ kháng cáo nào</strong>
              <span>Không có tài khoản nào bị khóa đang yêu cầu mở lại.</span>
            </div>
          ) : (
            <div className="mp-list">
              {appeals.map((a) => (
                <div key={a.request_id} className="card" style={{ padding: 18, marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <b style={{ fontSize: '1.1rem' }}>{a.user_email}</b>
                        <span className={`badge badge-${a.status === 'PENDING' ? 'warn' : a.status === 'APPROVED' ? 'ok' : 'muted'}`}>
                          {a.status}
                        </span>
                      </div>
                      <div className="hint" style={{ marginTop: 4 }}>
                        SĐT chính chủ: <b>{a.contact_phone}</b> {a.other_phone && `· SĐT phụ: ${a.other_phone}`} · Nộp: {new Date(a.submit_at).toLocaleString('vi-VN')}
                      </div>
                      {a.note && <div style={{ marginTop: 8 }}>Lời giải trình: <i>{a.note}</i></div>}
                    </div>

                    {a.status === 'PENDING' && (
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-primary btn-sm" onClick={() => handleApproveAppeal(a.request_id)}>
                          <Icon name="check" size={14} /> Mở khóa tài khoản
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => handleRejectAppeal(a.request_id)}>
                          <Icon name="x" size={14} /> Từ chối
                        </button>
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 14 }}>
                    <div>
                      <span className="hint">Mặt trước CCCD</span>
                      <a href={mediaUrl(a.cccd_front_url)} target="_blank" rel="noreferrer">
                        <img src={mediaUrl(a.cccd_front_url)} alt="CCCD Trước" style={{ width: '100%', height: 110, objectFit: 'cover', borderRadius: 4, marginTop: 4 }} />
                      </a>
                    </div>
                    <div>
                      <span className="hint">Mặt sau CCCD</span>
                      <a href={mediaUrl(a.cccd_back_url)} target="_blank" rel="noreferrer">
                        <img src={mediaUrl(a.cccd_back_url)} alt="CCCD Sau" style={{ width: '100%', height: 110, objectFit: 'cover', borderRadius: 4, marginTop: 4 }} />
                      </a>
                    </div>
                    <div>
                      <span className="hint">Tra cứu SIM chính chủ</span>
                      <a href={mediaUrl(a.sim_ownership_url)} target="_blank" rel="noreferrer">
                        <img src={mediaUrl(a.sim_ownership_url)} alt="SIM" style={{ width: '100%', height: 110, objectFit: 'cover', borderRadius: 4, marginTop: 4 }} />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* MODAL TỪ CHỐI TIN ĐĂNG */}
      {rejectProd && (
        <div className="modal-back" onClick={() => setRejectProd(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleRejectProdSubmit}>
            <h3>Từ chối tin đăng “{rejectProd.title}”</h3>
            <p className="hint">Người bán sẽ nhận được thông báo kèm lý do từ chối để chỉnh sửa lại tin.</p>
            <div className="field">
              <label htmlFor="rej-r">Lý do từ chối (*)</label>
              <textarea
                id="rej-r"
                className="textarea"
                required
                minLength={10}
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="VD: Ảnh chụp quá mờ, tiêu đề chứa từ ngữ spam hoặc giá đăng không hợp lý..."
              />
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setRejectProd(null)}>Hủy</button>
              <button className="btn btn-danger" disabled={busy}>{busy ? 'Đang gửi...' : 'Xác nhận từ chối'}</button>
            </div>
          </form>
        </div>
      )}

      {/* MODAL XỬ LÝ TỐ CÁO */}
      {resolveRep && (
        <div className="modal-back" onClick={() => setResolveRep(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleResolveReportSubmit}>
            <h3>Xử lý tố cáo #{resolveRep.report_id}</h3>
            <div className="field">
              <label htmlFor="res-act">Biện pháp chế tài thực hiện (*)</label>
              <input
                id="res-act"
                className="input"
                required
                minLength={5}
                value={resolveAction}
                onChange={(e) => setResolveAction(e.target.value)}
                placeholder="VD: Đã gỡ bài đăng vi phạm, gửi cảnh cáo người bán..."
              />
            </div>
            <div style={{ display: 'grid', gap: 10, margin: '14px 0' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="checkbox" checked={delTargetChecked} onChange={(e) => setDelTargetChecked(e.target.checked)} />
                Xóa tin đăng / bình luận bị tố cáo
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#c0392b' }}>
                <input type="checkbox" checked={banUserChecked} onChange={(e) => setBanUserChecked(e.target.checked)} />
                Khóa vĩnh viễn tài khoản người bị tố cáo
              </label>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setResolveRep(null)}>Hủy</button>
              <button className="btn btn-danger" disabled={busy}>{busy ? 'Đang lưu...' : 'Thực hiện chế tài'}</button>
            </div>
          </form>
        </div>
      )}

      {/* MODAL BÁC BỎ TỐ CÁO */}
      {dismissRep && (
        <div className="modal-back" onClick={() => setDismissRep(null)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleDismissReportSubmit}>
            <h3>Bác bỏ tố cáo #{dismissRep.report_id}</h3>
            <div className="field">
              <label htmlFor="dis-r">Lý do bác bỏ (*)</label>
              <textarea
                id="dis-r"
                className="textarea"
                required
                minLength={10}
                rows={3}
                value={dismissReason}
                onChange={(e) => setDismissReason(e.target.value)}
                placeholder="VD: Nội dung bài đăng hợp lệ, không vi phạm quy chế sàn..."
              />
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setDismissRep(null)}>Hủy</button>
              <button className="btn btn-primary" disabled={busy}>{busy ? 'Đang lưu...' : 'Xác nhận bác bỏ'}</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
