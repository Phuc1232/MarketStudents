-- ============================================================================
-- UNI MARKET - SEED TEST DATA SCRIPT CHO POSTGRESQL
-- Phục vụ kiểm thử toàn diện các API: Auth, User, Masterdata, Product, Interaction
-- Khớp 100% với DDL trong fullconfigfordb.txt
-- Mật khẩu mặc định cho TẤT CẢ tài khoản test: password123
-- (Hash Argon2: $argon2id$v=19$m=65536,t=3,p=4$mSZlfxLMraFUPyc6hjO/jQ$0pURkZQKq/bK9Ud9MHhDMjIR0XP3tBBNIS3CeCb2+hc)
-- ============================================================================

BEGIN;

-- 1. BẢNG ROLES (PHÂN QUYỀN)
INSERT INTO public.roles (role_id, role_name) VALUES 
(1, 'Admin'),
(2, 'User'),
(3, 'Student'),
(4, 'Staff')
ON CONFLICT (role_id) DO UPDATE SET role_name = EXCLUDED.role_name;

-- 2. BẢNG PRODUCT_CONDITION (TÌNH TRẠNG HÀNG HÓA)
INSERT INTO public.product_condition (condition_id, condition_name, "desc") VALUES 
(1, 'Mới 100%', 'Hàng mới nguyên seal, chưa từng qua sử dụng'),
(2, 'Như mới 99%', 'Đã khui hộp, dùng lướt vài lần, không trầy xước'),
(3, 'Đã qua sử dụng (90-95%)', 'Còn hoạt động rất tốt, có hao mòn nhẹ theo thời gian'),
(4, 'Cũ / Cần tân trang', 'Ngoại hình cũ hoặc cần bảo dưỡng lại')
ON CONFLICT (condition_id) DO UPDATE SET condition_name = EXCLUDED.condition_name, "desc" = EXCLUDED."desc";

-- 3. BẢNG PRODUCT_STATUSES (TRẠNG THÁI BÀI ĐĂNG)
INSERT INTO public.product_statuses (status_id, status_name, color_code) VALUES 
(1, 'Pending_Approval', '#FFA500'),
(2, 'Active', '#008000'),
(3, 'Sold', '#808080'),
(4, 'Hidden', '#333333'),
(5, 'Rejected', '#FF0000')
ON CONFLICT (status_id) DO UPDATE SET status_name = EXCLUDED.status_name, color_code = EXCLUDED.color_code;

-- 4. BẢNG REPORT_REASON (LÝ DO BÁO CÁO VI PHẠM)
INSERT INTO public.report_reason (reason_id, "content") VALUES 
(1, 'Lừa đảo, không giao hàng hoặc nhận cọc rồi chặn liên lạc'),
(2, 'Hàng giả, hàng nhái kém chất lượng'),
(3, 'Hàng cấm buôn bán theo quy định pháp luật và trường học'),
(4, 'Spam, đăng tin trùng lặp nhiều lần'),
(5, 'Thông tin sản phẩm hoặc giá cả sai sự thật')
ON CONFLICT (reason_id) DO UPDATE SET "content" = EXCLUDED."content";

-- 5. BẢNG SERVICE_PACKAGES (GÓI DỊCH VỤ ĐẨY TIN CHO SINH VIÊN)
INSERT INTO public.service_packages (package_id, package_name, price, duration, student_discount) VALUES 
(1, 'Gói Đẩy Tin Nhanh 3 Ngày', 15000, 3, 0.3),
(2, 'Gói Ghim Tin VIP Trang Chủ 7 Ngày', 35000, 7, 0.4),
(3, 'Gói Pro Seller Tháng', 99000, 30, 0.5)
ON CONFLICT (package_id) DO UPDATE SET package_name = EXCLUDED.package_name, price = EXCLUDED.price;

-- 6. ĐỊA GIỚI HÀNH CHÍNH (MASTER DATA)
-- 6.1 Tỉnh/Thành
INSERT INTO public.master_provinces (province_id, province_name, province_type, code) VALUES 
(79, 'Thành phố Hồ Chí Minh', 'Thành phố Trung ương', '79'),
(1, 'Thành phố Hà Nội', 'Thành phố Trung ương', '01'),
(48, 'Thành phố Đà Nẵng', 'Thành phố Trung ương', '48'),
(92, 'Thành phố Cần Thơ', 'Thành phố Trung ương', '92')
ON CONFLICT (province_id) DO UPDATE SET province_name = EXCLUDED.province_name;

-- 6.2 Quận/Huyện
INSERT INTO public.master_districts (district_id, province_id, district_name, district_type) VALUES 
(760, 79, 'Quận 1', 'Quận'),
(769, 79, 'Thành phố Thủ Đức', 'Thành phố'),
(765, 79, 'Quận Bình Thạnh', 'Quận'),
(770, 79, 'Quận Gò Vấp', 'Quận'),
(1, 1, 'Quận Ba Đình', 'Quận'),
(5, 1, 'Quận Cầu Giấy', 'Quận')
ON CONFLICT (district_id) DO UPDATE SET district_name = EXCLUDED.district_name;

-- 6.3 Phường/Xã
INSERT INTO public.master_wards (ward_id, district_id, ward_name, ward_type) VALUES 
(26734, 760, 'Phường Bến Nghé', 'Phường'),
(26740, 760, 'Phường Bến Thành', 'Phường'),
(26800, 769, 'Phường Linh Trung (Khu ĐHQG)', 'Phường'),
(26805, 769, 'Phường Tăng Nhơn Phú A', 'Phường'),
(26810, 769, 'Phường Hiệp Phú', 'Phường'),
(26890, 765, 'Phường 25', 'Phường'),
(100, 5, 'Phường Dịch Vọng Hậu', 'Phường')
ON CONFLICT (ward_id) DO UPDATE SET ward_name = EXCLUDED.ward_name;

-- 7. DANH MỤC SẢN PHẨM & THUỘC TÍNH ĐỘNG (EAV)
-- 7.1 Danh mục chính
INSERT INTO public.categories (category_id, "name", slug, icon_url) VALUES 
(1, 'Sách & Giáo trình Đại học', 'sach-giao-trinh', 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=100'),
(2, 'Đồ điện tử & Công nghệ', 'do-dien-tu', 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=100'),
(3, 'Đồ gia dụng & Phòng trọ', 'do-gia-dung', 'https://images.unsplash.com/photo-1583847268964-b28dc8f51f92?w=100'),
(4, 'Phương tiện di chuyển', 'xe-co', 'https://images.unsplash.com/photo-1558981403-c5f9899a28bc?w=100')
ON CONFLICT (category_id) DO UPDATE SET "name" = EXCLUDED."name";

-- 7.2 Danh mục con
INSERT INTO public.sub_categories (sub_category_id, category_id, "name") VALUES 
(1, 1, 'Giáo trình & Bài tập lớn'),
(2, 1, 'Sách Ngoại ngữ & Luyện thi'),
(3, 1, 'Tiểu thuyết & Kỹ năng sống'),
(4, 2, 'Laptop & Máy tính bảng'),
(5, 2, 'Điện thoại thông minh'),
(6, 2, 'Phụ kiện máy tính (Chuột, Phím, Tai nghe)'),
(7, 3, 'Nồi cơm điện & Bếp từ'),
(8, 3, 'Quạt điện & Đèn bàn học'),
(9, 4, 'Xe máy số / Xe tay ga'),
(10, 4, 'Xe đạp & Xe đạp điện')
ON CONFLICT (sub_category_id) DO UPDATE SET "name" = EXCLUDED."name";

-- 7.3 Thuộc tính động (Attributes)
INSERT INTO public."attributes" (attribute_id, "name", data_type, subcategory_id) VALUES 
(1, 'RAM', 'select', 4),
(2, 'Dung lượng ổ cứng SSD', 'select', 4),
(3, 'Bộ vi xử lý (CPU)', 'select', 4),
(4, 'Dung lượng bộ nhớ trong', 'select', 5),
(5, 'Chuyên ngành học', 'select', 1),
(6, 'Năm xuất bản', 'number', 1)
ON CONFLICT (attribute_id) DO UPDATE SET "name" = EXCLUDED."name";

-- 7.4 Tùy chọn giá trị thuộc tính (Attribute Options)
INSERT INTO public.attribute_options (option_id, attribute_id, option_value) VALUES 
(1, 1, '8 GB'),
(2, 1, '16 GB'),
(3, 1, '32 GB'),
(4, 2, '256 GB SSD'),
(5, 2, '512 GB SSD'),
(6, 2, '1 TB SSD'),
(7, 3, 'Intel Core i5'),
(8, 3, 'Intel Core i7'),
(9, 3, 'Apple M1 / M2 / M3'),
(10, 4, '64 GB'),
(11, 4, '128 GB'),
(12, 4, '256 GB'),
(13, 5, 'Công nghệ thông tin & Viễn thông'),
(14, 5, 'Kinh tế & Quản trị kinh doanh'),
(15, 5, 'Kỹ thuật & Cơ khí')
ON CONFLICT (option_id) DO UPDATE SET option_value = EXCLUDED.option_value;

-- 8. TÀI KHOẢN NGƯỜI DÙNG (USERS)
-- Mật khẩu của TẤT CẢ user dưới đây là: password123
INSERT INTO public."user" (id, "Email", "PassWord", "isActive", account_type, role_id) VALUES 
(1, 'admin@unimarket.edu.vn', '$argon2id$v=19$m=65536,t=3,p=4$mSZlfxLMraFUPyc6hjO/jQ$0pURkZQKq/bK9Ud9MHhDMjIR0XP3tBBNIS3CeCb2+hc', true, 'Admin', 1),
(2, 'phucthien@ut.edu.vn', '$argon2id$v=19$m=65536,t=3,p=4$mSZlfxLMraFUPyc6hjO/jQ$0pURkZQKq/bK9Ud9MHhDMjIR0XP3tBBNIS3CeCb2+hc', true, 'Sinh Vien', 3),
(3, 'linh.nguyen@hcmut.edu.vn', '$argon2id$v=19$m=65536,t=3,p=4$mSZlfxLMraFUPyc6hjO/jQ$0pURkZQKq/bK9Ud9MHhDMjIR0XP3tBBNIS3CeCb2+hc', true, 'Sinh Vien', 3),
(4, 'quang.seller@gmail.com', '$argon2id$v=19$m=65536,t=3,p=4$mSZlfxLMraFUPyc6hjO/jQ$0pURkZQKq/bK9Ud9MHhDMjIR0XP3tBBNIS3CeCb2+hc', true, 'Ban Chuyen', 2),
(5, 'buyer_test@gmail.com', '$argon2id$v=19$m=65536,t=3,p=4$mSZlfxLMraFUPyc6hjO/jQ$0pURkZQKq/bK9Ud9MHhDMjIR0XP3tBBNIS3CeCb2+hc', true, 'Ca Nhan', 2)
ON CONFLICT (id) DO UPDATE SET "Email" = EXCLUDED."Email", "PassWord" = EXCLUDED."PassWord";

-- 9. HỒ SƠ NGƯỜI DÙNG (USER PROFILES)
INSERT INTO public.user_profiles (user_id, first_name, last_name, phone_number, avatar_url, bio, type_mode) VALUES 
(1, 'Admin', 'UniMarket', '0901000001', 'https://api.dicebear.com/7.x/bottts/svg?seed=admin', 'Quản trị viên hệ thống UniMarket', 'dark'),
(2, 'Phúc', 'Trần Thiện', '0912345678', 'https://api.dicebear.com/7.x/avataaars/svg?seed=phuc', 'Sinh viên UTE K21 - Khoa CNTT', 'dark'),
(3, 'Linh', 'Nguyễn Thảo', '0923456789', 'https://api.dicebear.com/7.x/avataaars/svg?seed=linh', 'Sinh viên ĐH Bách Khoa TP.HCM', 'light'),
(4, 'Quang', 'Lê Hữu', '0934567890', 'https://api.dicebear.com/7.x/avataaars/svg?seed=quang', 'Chuyên thanh lý máy tính và sách cũ giá sinh viên', 'light'),
(5, 'Hải', 'Đặng Quốc', '0945678901', 'https://api.dicebear.com/7.x/avataaars/svg?seed=hai', 'Cần tìm mua giáo trình và laptop học đồ họa', 'light')
ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name, phone_number = EXCLUDED.phone_number;

-- 10. THỐNG KÊ NGƯỜI DÙNG (USER STATS)
INSERT INTO public.user_stats (user_id, rating_avg, response_rate, joined_date) VALUES 
(1, 5.0, 100.0, NOW() - INTERVAL '180 days'),
(2, 4.9, 98.5, NOW() - INTERVAL '90 days'),
(3, 4.8, 95.0, NOW() - INTERVAL '60 days'),
(4, 4.6, 90.0, NOW() - INTERVAL '120 days'),
(5, 5.0, 100.0, NOW() - INTERVAL '15 days')
ON CONFLICT (user_id) DO UPDATE SET rating_avg = EXCLUDED.rating_avg;

-- 11. XÁC THỰC SINH VIÊN (STUDENT VERIFICATIONS)
INSERT INTO public.student_verifications (user_id, edu_email, student_card_img, status, submitted_at) VALUES 
(2, 'phucthien@ut.edu.vn', 'https://example.com/cards/card_phuc.jpg', 'Verified', NOW() - INTERVAL '90 days'),
(3, 'linh.nguyen@hcmut.edu.vn', 'https://example.com/cards/card_linh.jpg', 'Verified', NOW() - INTERVAL '60 days')
ON CONFLICT (user_id) DO UPDATE SET status = EXCLUDED.status;

-- 12. VÍ TIỀN NGƯỜI DÙNG (WALLETS)
INSERT INTO public.wallets (wallet_id, user_id, currency) VALUES 
(1, 1, 10000000.0),
(2, 2, 150000.0),
(3, 3, 200000.0),
(4, 4, 500000.0),
(5, 5, 50000.0)
ON CONFLICT (wallet_id) DO UPDATE SET currency = EXCLUDED.currency;

-- 13. SẢN PHẨM TIN ĐĂNG (PRODUCTS)
INSERT INTO public.products (
    product_id, seller_id, sub_category_id, status_id, condition_id, buyer_id, 
    title, price, description, thumbnails, deleted_at, "CreatedAt", "UpdateAt"
) VALUES 
(
    1, 2, 4, 2, 2, NULL,
    'Laptop Dell Inspiron 5510 i5 Gen 11 16GB RAM mượt mà cho sinh viên CNTT',
    9500000,
    'Máy mình dùng học lập trình 1 năm, ngoại hình đẹp 98%, pin trâu 4-5 tiếng, phím led gõ êm, màn hình Full HD sắc nét. Tặng kèm chuột không dây và túi chống sốc.',
    'https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=600',
    NULL, NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'
),
(
    2, 3, 4, 2, 2, NULL,
    'Macbook Air M1 2020 8GB/256GB Gold chính hãng SA/A pin 92%',
    12800000,
    'Đổi sang máy bàn nên cần nhượng lại Macbook Air M1 màu vàng hồng. Máy nữ dùng kỹ, dán màn hình và kê tay từ đầu, sạc cáp zin theo hộp đầy đủ.',
    'https://images.unsplash.com/photo-1611186871348-b1ce696e52c9?w=600',
    NULL, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
),
(
    3, 2, 1, 2, 3, NULL,
    'Combo Giáo trình Cấu trúc Dữ liệu & Giải thuật + Lập trình C++ ĐHQG',
    80000,
    'Bộ sách còn rất mới, có note bút chì bài giải chi tiết các kỳ thi trước, nhượng lại giá rẻ cho các bạn khóa dưới ôn thi môn chuyên ngành.',
    'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600',
    NULL, NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days'
),
(
    4, 4, 7, 2, 2, NULL,
    'Bếp từ Sunhouse kèm nồi lẩu cho sinh viên ở trọ nấu ăn nhanh',
    250000,
    'Bếp còn dùng tốt, điều khiển cảm ứng, hẹn giờ nấu, tiết kiệm điện. Phù hợp 1-2 bạn ở trọ.',
    'https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=600',
    NULL, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'
),
(
    5, 4, 9, 3, 3, 5,
    'Xe máy Honda Wave Alpha 2018 biển số Sài Gòn máy êm ru',
    9800000,
    'Xe chạy giữ gìn, thay nhớt định kỳ mỗi 1500km, xe tiết kiệm xăng phù hợp bạn nào đi học hoặc chạy thêm xe công nghệ.',
    'https://images.unsplash.com/photo-1558981403-c5f9899a28bc?w=600',
    NULL, NOW() - INTERVAL '15 days', NOW() - INTERVAL '10 days'
),
(
    6, 3, 2, 2, 2, NULL,
    'Bộ tài liệu luyện thi TOEIC ETS 2024 mới nhất có Audio bài nghe',
    95000,
    'Sách in bìa màu sắc nét, kèm link Google Drive full Audio trọn bộ đề thi thử kèm đáp án chi tiết.',
    'https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=600',
    NULL, NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
)
ON CONFLICT (product_id) DO UPDATE SET title = EXCLUDED.title, price = EXCLUDED.price;

-- 14. ẢNH CHI TIẾT SẢN PHẨM (PRODUCT IMAGES)
INSERT INTO public.product_images (image_id, product_id, image_url, display_order, is_thumbnail) VALUES 
(1, 1, 'https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=600', 0, true),
(2, 1, 'https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=600', 1, false),
(3, 2, 'https://images.unsplash.com/photo-1611186871348-b1ce696e52c9?w=600', 0, true),
(4, 2, 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600', 1, false),
(5, 3, 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600', 0, true),
(6, 4, 'https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=600', 0, true),
(7, 5, 'https://images.unsplash.com/photo-1558981403-c5f9899a28bc?w=600', 0, true),
(8, 6, 'https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=600', 0, true)
ON CONFLICT (image_id) DO UPDATE SET image_url = EXCLUDED.image_url;

-- 15. THUỘC TÍNH ĐỘNG CỦA SẢN PHẨM (PRODUCT ATTRIBUTES)
INSERT INTO public.product_attributes (id, product_id, attribute_id, "Value_Text", "Value_Num") VALUES 
(1, 1, 1, '16 GB', '16'),
(2, 1, 2, '512 GB SSD', '512'),
(3, 1, 3, 'Intel Core i5', ''),
(4, 2, 1, '8 GB', '8'),
(5, 2, 2, '256 GB SSD', '256'),
(6, 2, 3, 'Apple M1 / M2 / M3', ''),
(7, 3, 5, 'Công nghệ thông tin & Viễn thông', ''),
(8, 3, 6, '2023', '2023')
ON CONFLICT (id) DO UPDATE SET "Value_Text" = EXCLUDED."Value_Text";

-- 16. ĐỊA CHỈ GIAO DỊCH (ADDRESSES)
-- Bao gồm cả địa chỉ cá nhân người dùng và địa chỉ gắn với sản phẩm tin đăng
INSERT INTO public.addresses (address_id, user_id, product_id, ward_id, specific_name, "type", is_default) VALUES 
(1, 2, NULL, 26800, 'Ký túc xá Khu B ĐHQG, Tòa BA2', 'Ký túc xá', true),
(2, 3, NULL, 26734, 'Phòng trọ 124 Đinh Tiên Hoàng', 'Nhà riêng', true),
(3, 4, NULL, 26890, 'Số 45 Đường D2 (Nguyễn Gia Trí)', 'Cửa hàng', true),
(4, 2, 1, 26800, 'Cổng KTX Khu B, TP. Thủ Đức', 'Giao dịch', false),
(5, 3, 2, 26734, 'Quán Cafe The Coffee House Đinh Tiên Hoàng, Quận 1', 'Giao dịch', false),
(6, 2, 3, 26800, 'Trường ĐH Bách Khoa Cơ sở 2', 'Giao dịch', false),
(7, 4, 4, 26890, 'Hẻm 45 Đường D2, Bình Thạnh', 'Giao dịch', false)
ON CONFLICT (address_id) DO UPDATE SET specific_name = EXCLUDED.specific_name;

-- 17. SẢN PHẨM YÊU THÍCH (FAVORITES)
INSERT INTO public.favorites (user_id, product_id, created_at) VALUES 
(3, 1, NOW() - INTERVAL '2 days'),
(5, 1, NOW() - INTERVAL '1 day'),
(5, 2, NOW() - INTERVAL '3 hours'),
(2, 4, NOW() - INTERVAL '5 hours')
ON CONFLICT (user_id, product_id) DO NOTHING;

-- 18. BÌNH LUẬN TRÊN SẢN PHẨM (COMMENTS)
INSERT INTO public."comments" (comment_id, product_id, user_id, "content", parent_id, "CreatedAt", "UpdateAt") VALUES 
(1, 1, 5, 'Anh ơi máy còn bảo hành hãng hay đã hết hạn bảo hành rồi ạ?', NULL, NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'),
(2, 1, 2, 'Máy vừa hết bảo hành tháng trước bạn nhé, nhưng mình bao test 7 ngày lỗi hoàn tiền!', 1, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'),
(3, 2, 5, 'Có fix nhẹ tiền xăng xe cho sinh viên qua tận nơi lấy không bạn?', NULL, NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day'),
(4, 2, 3, 'Sinh viên nhiệt tình mình bớt 200k nhé bạn ơi!', 3, NOW() - INTERVAL '12 hours', NOW() - INTERVAL '12 hours')
ON CONFLICT (comment_id) DO UPDATE SET "content" = EXCLUDED."content";

-- 19. HỘI THOẠI CHAT (CONVERSATIONS & PARTICIPATION & MESSAGES)
INSERT INTO public.conversations (conversation_id, product_id, last_message_at) VALUES 
(1, 1, NOW() - INTERVAL '1 hour')
ON CONFLICT (conversation_id) DO UPDATE SET last_message_at = EXCLUDED.last_message_at;

INSERT INTO public."Participation" (buyer_id, seller_id, conversation_id) VALUES 
(5, 2, 1)
ON CONFLICT (buyer_id, seller_id, conversation_id) DO NOTHING;

INSERT INTO public.messages (message_id, conversation_id, sender_id, "content", is_read, sent_at) VALUES 
(1, 1, 5, 'Chào bạn, chiều nay tầm 4h mình qua KTX Khu B xem laptop Dell được không bạn?', true, NOW() - INTERVAL '2 hours'),
(2, 1, 2, 'Được bạn nhé, đến cổng số 1 KTX Khu B bạn alo số 0912345678 mình đem máy xuống nha!', true, NOW() - INTERVAL '1 hour')
ON CONFLICT (message_id) DO UPDATE SET "content" = EXCLUDED."content";

-- 20. ĐỒNG BỘ GIÁ TRỊ SEQUENCE (CHỐNG LỖI DUPLICATE KEY KHI INSERT TỪ API SAU NÀY)
SELECT setval('public.roles_role_id_seq', (SELECT COALESCE(MAX(role_id), 1) FROM public.roles));
SELECT setval('public.product_condition_condition_id_seq', (SELECT COALESCE(MAX(condition_id), 1) FROM public.product_condition));
SELECT setval('public.product_statuses_status_id_seq', (SELECT COALESCE(MAX(status_id), 1) FROM public.product_statuses));
SELECT setval('public.report_reason_reason_id_seq', (SELECT COALESCE(MAX(reason_id), 1) FROM public.report_reason));
SELECT setval('public.service_packages_package_id_seq', (SELECT COALESCE(MAX(package_id), 1) FROM public.service_packages));
SELECT setval('public.master_provinces_province_id_seq', (SELECT COALESCE(MAX(province_id), 1) FROM public.master_provinces));
SELECT setval('public.master_districts_district_id_seq', (SELECT COALESCE(MAX(district_id), 1) FROM public.master_districts));
SELECT setval('public.master_wards_ward_id_seq', (SELECT COALESCE(MAX(ward_id), 1) FROM public.master_wards));
SELECT setval('public.categories_category_id_seq', (SELECT COALESCE(MAX(category_id), 1) FROM public.categories));
SELECT setval('public.sub_categories_sub_category_id_seq', (SELECT COALESCE(MAX(sub_category_id), 1) FROM public.sub_categories));
SELECT setval('public.attributes_attribute_id_seq', (SELECT COALESCE(MAX(attribute_id), 1) FROM public."attributes"));
SELECT setval('public.attribute_options_option_id_seq', (SELECT COALESCE(MAX(option_id), 1) FROM public.attribute_options));
SELECT setval('public.user_id_seq', (SELECT COALESCE(MAX(id), 1) FROM public."user"));
SELECT setval('public.wallets_wallet_id_seq', (SELECT COALESCE(MAX(wallet_id), 1) FROM public.wallets));
SELECT setval('public.products_product_id_seq', (SELECT COALESCE(MAX(product_id), 1) FROM public.products));
SELECT setval('public.product_images_image_id_seq', (SELECT COALESCE(MAX(image_id), 1) FROM public.product_images));
SELECT setval('public.product_attributes_id_seq', (SELECT COALESCE(MAX(id), 1) FROM public.product_attributes));
SELECT setval('public.addresses_address_id_seq', (SELECT COALESCE(MAX(address_id), 1) FROM public.addresses));
SELECT setval('public.comments_comment_id_seq', (SELECT COALESCE(MAX(comment_id), 1) FROM public."comments"));
SELECT setval('public.conversations_conversation_id_seq', (SELECT COALESCE(MAX(conversation_id), 1) FROM public.conversations));
SELECT setval('public.messages_message_id_seq', (SELECT COALESCE(MAX(message_id), 1) FROM public.messages));

COMMIT;
