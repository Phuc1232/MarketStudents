# UniMarket Infrastructure as Code (Terraform)

Thư mục này chứa toàn bộ mã nguồn định nghĩa hạ tầng đám mây **100% AWS** cho dự án **UniMarket**, phục vụ lưu trữ ảnh, xử lý ảnh hướng sự kiện (Event-Driven Lambda) và phân phối CDN tốc độ cao.

---

## 📁 Danh Sách File Trong Thư Mục

| Tên File | Vai trò |
| :--- | :--- |
| `provider.tf` | Khai báo nhà cung cấp AWS, phiên bản Terraform và Region mặc định (`ap-southeast-1`). |
| `variables.tf` | Định nghĩa các tham số cấu hình (tên dự án, môi trường, tùy chọn bật/tắt CloudFront). |
| `terraform.tfvars.example` | File mẫu để tham khảo giá trị cấu hình (an toàn để đưa lên GitHub). |
| `s3.tf` | Định nghĩa 2 Bucket: `media` (ảnh công khai) và `private-docs` (thẻ sinh viên bảo mật). |
| `lambda.tf` | Đóng gói và tạo hàm AWS Lambda tự động resize ảnh, cấp quyền IAM và gắn S3 Event Trigger. |
| `lambda_src/lambda_function.py` | Mã nguồn Python sử dụng Pillow để chuyển đổi ảnh sang WebP độ nét cao. |
| `cloudfront.tf` | Cấu hình mạng phân phối nội dung (CDN) với chuẩn bảo mật OAC mới nhất của AWS. |
| `outputs.tf` | Xuất ra các URL và tên Bucket để điền vào file `.env` của Backend/Frontend. |

---

## 🛡️ Quy Tắc Bảo Mật (Đã Cấu Hình Sẵn Trong `.gitignore`)

* File `terraform.tfvars` (chứa secret/password thật) và file `*.tfstate` (chứa dữ liệu trạng thái hạ tầng) đã được **chặn tuyệt đối khỏi Git**.
* **Không bao giờ xóa dòng chặn terraform trong `.gitignore`**.

---

## 🚀 Hướng Dẫn Chạy Thử Nghiệm (Khi bạn đã sẵn sàng)

> [!NOTE]
> Hiện tại toàn bộ file chỉ mới được tạo ở local để bạn kiểm tra, **chưa có bất kỳ lệnh nào được thực thi lên tài khoản AWS**.

Khi nào bạn muốn deploy thử lên AWS, chỉ cần thực hiện 3 lệnh sau:

1. **Khởi tạo Terraform:**
   ```bash
   cd terraform/S3
   terraform init
   ```

2. **Xem trước những gì sẽ được tạo (Dry-run, không tốn tiền):**
   ```bash
   terraform plan
   ```

3. **Áp dụng tạo tài nguyên lên AWS:**
   ```bash
   terraform apply
   ```

