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

## Giao diện điện thoại và kiểm thử responsive

CSS mobile nằm trong src/styles/mobile.css, nạp sau các CSS tính năng. Bố cục <=780px dùng điều hướng dưới, header gọn, bộ lọc thu gọn; chat có màn hình riêng và phản hồi theo visualViewport. Input 16px, form một cột, modal co theo vùng nhìn, viewport-fit=cover hỗ trợ safe-area. Grid sản phẩm hai cột từ 360px; dưới 360px dùng một cột. Tin của tôi có menu thao tác. Không đổi backend/database.

Chạy kiểm thử với Chromium:

```bash
npm ci
npx playwright install chromium
npm run test:responsive
```

Hoặc dùng Chrome có sẵn trên Windows:

```powershell
$env:PW_CHANNEL='chrome'
npm run test:responsive
```

Tests dùng API/WebSocket giả lập; không tác động dữ liệu thật. Kiểm tra 320/360/390/430/768/1024/1440px trên 10 trang, chat màn ngang thấp, gửi tin, mở/đóng thông báo và modal sửa tin. Ảnh chụp trang chủ mobile/desktop, chat và bàn phím giả lập lưu trong test-results/ (không commit).

Mô phỏng thay đổi visualViewport không thay thế bàn phím thiết bị thật. Cần kiểm tra thêm Safari iPhone/Chrome Android: bàn phím, xoay máy, phóng chữ, safe-area và gửi ảnh. Build production bằng npm run build.
