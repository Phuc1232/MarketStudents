# chợmình – Frontend (Market for Students)

React + TypeScript + Vite, nối với backend FastAPI `MarketStudents-master`.

## Chạy thử

```bash
# 1) Backend (cổng 8000)
cd MarketStudents-master
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# 2) Frontend (cổng 5173)
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173. Mọi request API đi qua tiền tố `/api` (Vite proxy → `localhost:8000`, gồm cả WebSocket),
nên không bị trùng với route giao diện như `/product`. Backend ở máy/cổng khác:
`VITE_BACKEND_URL=http://host:port npm run dev`. Khi deploy riêng: đặt `VITE_API_URL=https://api...`.

Dữ liệu mẫu: chạy `seed_test_data.sql` để có danh mục, tình trạng, trạng thái.

## Trang ↔ API

| Trang | File HTML | Route | API chính |
|---|---|---|---|
| Trang chủ | index.html | `/` | `GET /product`, `/masterdata/category/sub`, `/product/search/suggestions` |
| Đăng nhập / quên MK | login.html | `/login` | `POST /auth/login`, `/auth/forgot-password/*` |
| Đăng ký | register.html | `/register` | `POST /auth/register` |
| Chi tiết | product.html | `/product?id=` | `GET /product/{id}`, bình luận, yêu thích, theo dõi, nhắn tin |
| Đăng tin | post.html | `/post` | `POST /upload/images`, `POST /product`, masterdata |
| Tin của tôi | my-products.html | `/my-products` | `/product/me`, `/me/trash`, `/my-purchases`, sold/hide/restore |
| Yêu thích | favorites.html | `/favorites` | `/interaction/my-favorite` |
| Tin nhắn | messages.html | `/messages?c=` | `/interaction/conversations*`, WS `/ws/chat/{id}` |
| Thông báo | notifications.html | `/notifications` | `/interaction/notifications/*`, WS `/ws/notifications` |
| Tài khoản | profile.html | `/profile?tab=` | `/user/profile/me`, `/user/address/me`, `/user/verify-student/*` |
