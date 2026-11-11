import { useSyncExternalStore } from 'react'

/* ------------------------------------------------------------------ */
/*  Cấu hình                                                           */
/* ------------------------------------------------------------------ */
export const API: string = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api'
export const GOOGLE_CLIENT_ID: string =
  (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) ??
  '103759217585-02flg4jnr9ko84d9ogi5pde3vigvkegf.apps.googleusercontent.com'
const TOKEN_KEY = 'cm_token'

/* ------------------------------------------------------------------ */
/*  Token & trạng thái đăng nhập                                       */
/* ------------------------------------------------------------------ */
const listeners = new Set<() => void>()
export const getToken = () => localStorage.getItem(TOKEN_KEY)

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
  listeners.forEach((l) => l())
}

export function getUserId(): number | null {
  const t = getToken()
  if (!t) return null
  try {
    const payload = JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.user_id === 'number' ? payload.user_id : null
  } catch {
    return null
  }
}

export function getUserRole(): number | null {
  const t = getToken()
  if (!t) return null
  try {
    const payload = JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.role_id === 'number' ? payload.role_id : null
  } catch {
    return null
  }
}

export function getUserAccountType(): string | null {
  const t = getToken()
  if (!t) return null
  try {
    const payload = JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.account_type === 'string' ? payload.account_type : null
  } catch {
    return null
  }
}

export function useAuth() {
  const token = useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    getToken,
  )
  const roleId = token ? getUserRole() : null
  const accountType = token ? getUserAccountType() : null
  const isAdmin = roleId === 1 || roleId === 4 || accountType === 'Admin' || accountType === 'Staff'
  return {
    token,
    loggedIn: !!token,
    userId: token ? getUserId() : null,
    roleId,
    accountType,
    isAdmin,
    logout: () => setToken(null),
  }
}

/* ------------------------------------------------------------------ */
/*  HTTP client                                                        */
/* ------------------------------------------------------------------ */
export class ApiError extends Error {
  status: number
  data: unknown
  constructor(status: number, message: string, data?: unknown) {
    super(message)
    this.status = status
    this.data = data
  }
}

function extractMessage(data: any, fallback: string): string {
  const d = data?.detail ?? data
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d.map((e) => (e?.msg ? String(e.msg).replace(/^Value error, /, '') : JSON.stringify(e))).join('; ')
  }
  if (typeof d === 'object' && d.message) return d.message
  return fallback
}

type Query = Record<string, string | number | boolean | null | undefined>

function qs(params?: Query) {
  if (!params) return ''
  const sp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
  })
  const s = sp.toString()
  return s ? `?${s}` : ''
}

async function request<T>(method: string, path: string, opts: { params?: Query; json?: unknown; form?: URLSearchParams | FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.json)
  } else if (opts.form) {
    body = opts.form // trình duyệt tự đặt Content-Type
  }

  let res: Response
  try {
    res = await fetch(`${API}${path}${qs(opts.params)}`, { method, headers, body })
  } catch {
    throw new ApiError(0, 'Không kết nối được máy chủ. Hãy kiểm tra backend đã chạy chưa.')
  }

  const text = await res.text()
  let data: any = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }

  if (!res.ok) {
    if (res.status === 401 && token) setToken(null) // token hết hạn
    throw new ApiError(res.status, extractMessage(data, `Lỗi ${res.status}`), data)
  }
  return data as T
}

export const api = {
  get: <T>(path: string, params?: Query) => request<T>('GET', path, { params }),
  post: <T>(path: string, json?: unknown, params?: Query) => request<T>('POST', path, { json: json ?? undefined, params }),
  put: <T>(path: string, json?: unknown) => request<T>('PUT', path, { json }),
  patch: <T>(path: string, json?: unknown, params?: Query) => request<T>('PATCH', path, { json: json ?? undefined, params }),
  del: <T>(path: string) => request<T>('DELETE', path),
  upload: <T>(path: string, form: FormData) => request<T>('POST', path, { form }),
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>('POST', '/auth/login', {
      form: new URLSearchParams({ username: email, password }),
    }),
  loginGoogle: (id_token: string, access_token?: string, refresh_token?: string) =>
    request<{ access_token: string; token_type: string }>('POST', '/auth/login/google', {
      json: { id_token, access_token, refresh_token },
    }),
}

/* ------------------------------------------------------------------ */
/*  Tiện ích                                                           */
/* ------------------------------------------------------------------ */
export function mediaUrl(u?: string | null): string {
  if (!u) return ''
  if (/^(https?:|data:|blob:)/.test(u)) return u
  return `${API}${u.startsWith('/') ? '' : '/'}${u}`
}

export function wsUrl(path: string): string {
  const token = getToken() ?? ''
  const sep = path.includes('?') ? '&' : '?'
  let base: string
  if (/^https?:/.test(API)) base = API.replace(/^http/, 'ws')
  else base = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${API}`
  return `${base}${path}${sep}token=${encodeURIComponent(token)}`
}

export const fmtPrice = (n: number) => (n === 0 ? 'Miễn phí' : new Intl.NumberFormat('vi-VN').format(n) + ' ₫')

export function timeAgo(iso?: string | null): string {
  if (!iso) return ''
  // Backend trả datetime UTC không kèm múi giờ → coi như UTC
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z')
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000)
  if (s < 60) return 'Vừa xong'
  if (s < 3600) return `${Math.floor(s / 60)} phút trước`
  if (s < 86400) return `${Math.floor(s / 3600)} giờ trước`
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} ngày trước`
  return d.toLocaleDateString('vi-VN')
}

export const CONDITIONS: Record<number, string> = {
  1: 'Mới 100%',
  2: 'Như mới 99%',
  3: 'Đã dùng 90–95%',
  4: 'Cũ / cần tân trang',
}

export const STATUSES: Record<number, { label: string; tone: 'warn' | 'ok' | 'muted' | 'off' | 'bad' }> = {
  1: { label: 'Chờ duyệt', tone: 'warn' },
  2: { label: 'Đang bán', tone: 'ok' },
  3: { label: 'Đã bán', tone: 'muted' },
  4: { label: 'Tạm ẩn', tone: 'off' },
  5: { label: 'Bị từ chối', tone: 'bad' },
}

export function toast(message: string, kind: 'ok' | 'err' = 'ok') {
  window.dispatchEvent(new CustomEvent('cm:toast', { detail: { message, kind } }))
}

export const errText = (e: unknown) => (e instanceof Error ? e.message : 'Đã có lỗi xảy ra')

/* ------------------------------------------------------------------ */
/*  Kiểu dữ liệu (khớp schemas của backend)                            */
/* ------------------------------------------------------------------ */
export interface ProductListItem {
  product_id: number
  title: string
  price: number
  thumbnails?: string | null
  sub_category_id: number
  status_id: number
  condition_id: number
  seller_id: number
  view_count: number
  CreatedAt?: string | null
}
export interface Paginated<T> { total: number; page: number; page_size: number; items: T[] }
export interface ProductImage { image_id: number; image_url: string; display_order: number; is_thumbnail: boolean }
export interface ProductDetail extends ProductListItem {
  description?: string | null
  buyer_id?: number | null
  seller?: { id: number; Email: string; account_type?: string | null } | null
  images: ProductImage[]
  value: { id: number; attribute_id: number; Value_Text?: string | null; Value_Num: string }[]
}
export interface Category { category_id: number; name: string; slug?: string; icon_url?: string; subcategories: { sub_category_id: number; category_id: number; name: string }[] }
export interface Attribute { attribute_id: number; name?: string; data_type?: string; option: { option_id: number; option_value: string }[] }
export interface Province { province_id: number; province_name: string }
export interface District { district_id: number; district_name?: string; province_id: number }
export interface Ward { ward_id: number; ward_name: string; district_id: number }
