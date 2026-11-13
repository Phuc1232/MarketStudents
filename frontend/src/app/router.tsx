import { createBrowserRouter, Link, Navigate, Outlet, RouteObject, useLocation, useParams } from 'react-router-dom'
import type { ReactElement } from 'react'
import MainLayout from '../components/layouts/MainLayout'
import MessageNotification from '../components/ui/MessageNotification'
import Toaster from '../components/ui/Toaster'
import { useAuth } from '../lib/api'
import Login from '../features/auth/Login'
import Register from '../features/auth/Register'
import Appeal from '../features/auth/Appeal'
import Home from '../features/products/Home'
import ProductDetail from '../features/products/ProductDetail'
import PostProduct from '../features/products/PostProduct'
import MyProducts from '../features/products/MyProducts'
import Favorites from '../features/products/Favorites'
import Messages from '../features/chat/Messages'
import Notifications from '../features/notifications/Notifications'
import Profile from '../features/users/Profile'
import SellerProfile from '../features/users/SellerProfile'
import AdminPortal from '../features/admin/AdminPortal'

/** Chặn trang cần đăng nhập → đẩy về /login và quay lại sau khi đăng nhập. */
function RequireAuth({ children }: { children: ReactElement }) {
  const { loggedIn } = useAuth()
  const loc = useLocation()
  if (!loggedIn) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />
  return children
}

/** Chặn trang Admin: Chỉ cho phép tài khoản Admin/Staff (role 1, 4) truy cập; các tài khoản khác bị đẩy về trang chủ. */
function RequireAdmin({ children }: { children: ReactElement }) {
  const { loggedIn, isAdmin } = useAuth()
  const loc = useLocation()
  if (!loggedIn) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />
  if (!isAdmin) return <Navigate to="/" replace />
  return children
}

function NotFound() {
  return (
    <div className="container page-empty">
      <h1>Không tìm thấy trang</h1>
      <p>Đường dẫn này không tồn tại.</p>
      <Link to="/" className="btn btn-primary">Về trang chủ</Link>
    </div>
  )
}

/** Keep notifications already stored with the old paths usable. */
function LegacyDetail({ kind }: { kind: 'product' | 'seller' }) {
  const { id } = useParams()
  const loc = useLocation()
  const query = new URLSearchParams(loc.search)
  query.set('id', id ?? '')
  return <Navigate to={`/${kind}?${query.toString()}${loc.hash}`} replace />
}

function ProductPage() {
  const loc = useLocation()
  const query = new URLSearchParams(loc.search)
  const id = Number(query.get('id'))
  if (query.get('open_review') === 'true' && Number.isSafeInteger(id) && id > 0) {
    return <Navigate to={`/my-products?tab=bought&review=${id}`} replace />
  }
  return <ProductDetail />
}

/** Mỗi trang có 2 đường dẫn: /login và /login.html (khớp các file HTML ở thư mục gốc). */
function page(path: string, element: ReactElement, auth = false): RouteObject[] {
  const el = auth ? <RequireAuth>{element}</RequireAuth> : element
  if (path === '/') return [{ index: true, element: el }, { path: '/index.html', element: el }]
  return [{ path, element: el }, { path: `${path}.html`, element: el }]
}

function adminPage(path: string, element: ReactElement): RouteObject[] {
  const el = <RequireAdmin>{element}</RequireAdmin>
  return [{ path, element: el }, { path: `${path}.html`, element: el }]
}

function GlobalFeedback() {
  return <><Outlet /><MessageNotification /><Toaster /></>
}

export const router = createBrowserRouter([
  { element: <GlobalFeedback />, children: [
  // Trang độc lập không có header/footer của khách mua hàng
  ...page('/login', <Login />),
  ...page('/register', <Register />),
  ...page('/appeal', <Appeal />),
  ...adminPage('/admin', <AdminPortal />),
  {
    element: <MainLayout />,
    children: [
      ...page('/', <Home />),
      ...page('/product', <ProductPage />),
      { path: '/product/:id', element: <LegacyDetail kind="product" /> },
      { path: '/user/:id', element: <LegacyDetail kind="seller" /> },
      ...page('/post', <PostProduct />, true),
      ...page('/my-products', <MyProducts />, true),
      ...page('/favorites', <Favorites />, true),
      ...page('/messages', <Messages />, true),
      ...page('/notifications', <Notifications />, true),
      ...page('/profile', <Profile />, true),
      ...page('/seller', <SellerProfile />),
      { path: '*', element: <NotFound /> },
    ],
  },
  ] },
])
