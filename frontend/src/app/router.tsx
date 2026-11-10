import { createBrowserRouter, Link, Navigate, RouteObject, useLocation } from 'react-router-dom'
import type { ReactElement } from 'react'
import MainLayout from '../components/layouts/MainLayout'
import { useAuth } from '../lib/api'
import Login from '../features/auth/Login'
import Register from '../features/auth/Register'
import Home from '../features/products/Home'
import ProductDetail from '../features/products/ProductDetail'
import PostProduct from '../features/products/PostProduct'
import MyProducts from '../features/products/MyProducts'
import Favorites from '../features/products/Favorites'
import Messages from '../features/chat/Messages'
import Notifications from '../features/notifications/Notifications'
import Profile from '../features/users/Profile'

/** Chặn trang cần đăng nhập → đẩy về /login và quay lại sau khi đăng nhập. */
function RequireAuth({ children }: { children: ReactElement }) {
  const { loggedIn } = useAuth()
  const loc = useLocation()
  if (!loggedIn) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />
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

/** Mỗi trang có 2 đường dẫn: /login và /login.html (khớp các file HTML ở thư mục gốc). */
function page(path: string, element: ReactElement, auth = false): RouteObject[] {
  const el = auth ? <RequireAuth>{element}</RequireAuth> : element
  if (path === '/') return [{ index: true, element: el }, { path: '/index.html', element: el }]
  return [{ path, element: el }, { path: `${path}.html`, element: el }]
}

export const router = createBrowserRouter([
  // Trang không có header/footer
  ...page('/login', <Login />),
  ...page('/register', <Register />),
  {
    element: <MainLayout />,
    children: [
      ...page('/', <Home />),
      ...page('/product', <ProductDetail />),
      ...page('/post', <PostProduct />, true),
      ...page('/my-products', <MyProducts />, true),
      ...page('/favorites', <Favorites />, true),
      ...page('/messages', <Messages />, true),
      ...page('/notifications', <Notifications />, true),
      ...page('/profile', <Profile />, true),
      { path: '*', element: <NotFound /> },
    ],
  },
])
