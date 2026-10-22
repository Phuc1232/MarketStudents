from fastapi import APIRouter, Depends, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from datetime import datetime, timezone
from src.Core.database import SessionLocal
from src.api.deps import get_db
from src.modules.User.service import get_current_user, get_optional_user
from src.modules.Interaction.connection_manager import manager
from src.modules import (
    User,
    FavoriteToggleResponse,
    FavoriteStatusResponse,
    PaginatedFavoritesResponse,
    CommentCreate,
    CommentItemResponse,
    CommentTreeResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListItemResponse,
    MessageCreate,
    MessageResponseItem,
    PaginatedMessagesResponse,
    MessageResponse,
    ReviewCreate,
    ReviewResponse,
    SellerReviewsResponse,
    PotentialBuyerResponse,
    FollowToggleResponse,
    FollowStatusResponse,
    NotificationResponse,
    Notification
)
from src.modules.Interaction.services import (
    toggle_favorite_product,
    get_user_favorite,
    check_favorite_status,
    create_product_comment,
    get_product_comments_tree,
    delete_comment,
    get_or_create_conversation,
    get_my_conversations,
    get_conversation_messages,
    mark_messages_as_read,
    send_message_rest,
    authenticate_ws_token,
    verify_conversation_member,
    save_websocket_message,
    mark_websocket_messages_as_read,
    create_review_product,
    get_product_reviews,
    get_seller_reviews,
    get_potential_buyers_for_product,
    toggle_follow_user,
    check_follow_status,
    process_mark_sold_and_notify_buyer,
    get_user_notifications,
    get_unread_notifications_count,
    mark_notification_as_read,
    mark_all_notifications_as_read
)

router = APIRouter(
    prefix="/interaction",
    tags=["Interaction"]
)

@router.post("/product/{product_id}/favorite", 
            response_model=FavoriteToggleResponse,
            summary="Thả tim hoặc Bỏ thả tim một sản phẩm (Wishlist Toggle)"
)
def toggle_favorite (product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return toggle_favorite_product(user.id,product_id,db)

@router.get("/my-favorite", response_model= PaginatedFavoritesResponse, status_code =status.HTTP_200_OK)
def list_my_favorite(   page: int = Query(1, ge=1, description="Số trang hiện tại"),
                        page_size: int = Query(20, ge=1, le=100, description="Số lượng mục trên mỗi trang"),
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)
                    ):
    return get_user_favorite(user_id=user.id, page=page, page_size=page_size, db=db)

@router.get("/{product_id}/status", response_model=FavoriteStatusResponse, status_code = status.HTTP_200_OK)
def get_status_favorite (product_id: int,user: User =Depends(get_current_user), db: Session = Depends(get_db)):
    return check_favorite_status(user.id, product_id,db)


# ==============================================================================
# NESTED COMMENTS ENDPOINTS (TASK T3: AC-4, AC-5, AC-6, AC-7)
# ==============================================================================

@router.post(
    "/product/{product_id}/comments",
    response_model=CommentItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng bình luận mới hoặc phản hồi câu hỏi dưới bài đăng (AC-4, AC-5, Seq 16)"
)
async def post_comment(
    product_id: int,
    form: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    - **AC-4**: Nếu `parent_id = None` -> Tạo bình luận gốc mới.
    - **AC-5**: Nếu truyền `parent_id` hợp lệ -> Tạo câu trả lời (Reply).
    - Tự động chuẩn hóa độ sâu tối đa 2 cấp (BR-2).
    - Tự động tạo Notification và Push Real-time (Seq 16).
    """
    return await create_product_comment(
        user_id=user.id,
        product_id=product_id,
        form=form,
        db=db
    )


@router.get(
    "/product/{product_id}/comments",
    response_model=List[CommentTreeResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem cây bình luận đa cấp của sản phẩm (Public - AC-6)"
)
def list_comments_tree(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    - **AC-6**: Lấy danh sách bình luận phân cấp theo cây 2 tầng:
      Mỗi bình luận gốc sẽ chứa danh sách các phản hồi `replies`.
    - Endpoint công khai (Public), người dùng chưa đăng nhập vẫn xem được.
    """
    return get_product_comments_tree(
        product_id=product_id,
        db=db
    )


@router.delete(
    "/comments/{comment_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Xóa một bình luận (Chính chủ hoặc Người bán - AC-7)"
)
def remove_comment(
    comment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    - **AC-7**: Xóa bình luận khỏi hệ thống.
    - Chỉ cho phép Tác giả bình luận HOẶC Chủ tin đăng (Người bán) thực hiện.
    - Người khác cố xóa sẽ bị trả về lỗi `403 Forbidden`.
    """
    return delete_comment(
        comment_id=comment_id,
        user_id=user.id,
        db=db
    )


# ==============================================================================
# CHAT REST API ENDPOINTS (TASK T4: AC-8, AC-9)
# ==============================================================================

@router.post(
    "/conversations",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Khởi tạo hoặc Mở cuộc hội thoại trao đổi về sản phẩm (AC-8)"
)
def create_or_open_conversation(
    form: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    - **AC-8**: Người mua bấm chat với người bán tại trang sản phẩm.
    - Nếu hội thoại giữa 2 người trên sản phẩm này đã có -> Trả về hội thoại cũ.
    - Nếu chưa có -> Tạo mới Conversation & Participation.
    - Chặn người bán tự chat với chính mình (HTTP 400).
    """
    return get_or_create_conversation(buyer_id=user.id, form=form, db=db)


@router.get(
    "/conversations",
    response_model=List[ConversationListItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem danh sách các cuộc hội thoại (Hộp thư đến / Inbox) của tôi (AC-9)"
)
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    - **AC-9**: Trả về toàn bộ danh sách các cuộc trò chuyện người dùng tham gia.
    - Kèm thông tin tóm tắt sản phẩm, đối tác chat, tin nhắn cuối cùng và số tin chưa đọc.
    - Sắp xếp ưu tiên hội thoại có tương tác mới nhất lên đầu.
    """
    return get_my_conversations(user_id=user.id, db=db)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=PaginatedMessagesResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy lịch sử tin nhắn trong cuộc hội thoại có phân trang (AC-9)"
)
def list_messages(
    conversation_id: int,
    page: int = Query(1, ge=1, description="Số trang hiện tại"),
    page_size: int = Query(20, ge=1, le=100, description="Số tin nhắn mỗi trang"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    - **AC-9**: Xem lịch sử tin nhắn trong phòng chat.
    - Kiểm tra bảo mật: Chỉ Buyer hoặc Seller thuộc hội thoại mới được xem (HTTP 403 nếu cố truy cập trái phép).
    """
    return get_conversation_messages(
        conversation_id=conversation_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        db=db
    )


@router.patch(
    "/conversations/{conversation_id}/read",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Đánh dấu tất cả tin nhắn đối phương gửi là đã đọc (BR-6)"
)
def read_all_messages(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    - **BR-6**: Cập nhật trạng thái `is_read = True` cho tất cả tin nhắn đối phương gửi đến.
    - Giúp xóa chấm đỏ / thông báo tin nhắn chưa đọc trong hộp thư.
    """
    return mark_messages_as_read(
        conversation_id=conversation_id,
        user_id=user.id,
        db=db
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponseItem,
    status_code=status.HTTP_201_CREATED,
    summary="Gửi tin nhắn vào cuộc hội thoại qua REST API"
)
def send_message_http(
    conversation_id: int,
    form: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Gửi tin nhắn nhanh qua giao thức REST HTTP (Body JSON: {"content": "...", "attachments": [...]}).
    """
    return send_message_rest(
        conversation_id=conversation_id,
        user_id=user.id,
        form=form,
        db=db
    )


# ==============================================================================
# WEBSOCKET REAL-TIME CHAT ENDPOINT (TASK T5: AC-10, AC-11, AC-12)
# ==============================================================================

@router.websocket("/ws/chat/{conversation_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    conversation_id: int,
    token: Optional[str] = Query(None, description="JWT Bearer Token truyền qua Query Param")
):
    """
    Kênh WebSocket trao đổi tin nhắn thời gian thực hai chiều (Task T5).
    - URL kết nối: ws://localhost:8000/interaction/ws/chat/{conversation_id}?token={jwt_token}
    - Mã ngắt kết nối đặc thù (RFC 6455 Application Codes):
      + 4401: Token không hợp lệ, thiếu token hoặc token đã hết hạn (AC-11).
      + 4403: Người dùng không thuộc cuộc hội thoại này (AC-11).
    - Giao thức thông điệp Client -> Server (JSON):
      + Gửi tin: `{"action": "send_message", "content": "Nội dung...", "attachments": ["url1"]}`
      + Đọc tin: `{"action": "mark_read"}`
      + Heartbeat: `{"action": "ping"}`
    - Giao thức sự kiện Server -> Client (JSON Broadcast):
      + Tin nhắn mới: `{"type": "new_message", "data": {...}}` (AC-12).
      + Xác nhận đã đọc: `{"type": "read_receipt", "data": {...}}`.
      + Phản hồi nhịp tim: `{"type": "pong", "timestamp": "..."}`.
      + Thông báo lỗi: `{"type": "error", "message": "..."}`.
    """
    # --------------------------------------------------------------------------
    # 1. BẢO MẬT & XÁC THỰC HANDSHAKE (BR-5, AC-10, AC-11)
    # --------------------------------------------------------------------------
    # Mở DB Session ngắn hạn chỉ để kiểm tra quyền, sau đó đóng ngay để trả lại Connection Pool
    with SessionLocal() as db:
        user = authenticate_ws_token(token, db)
        if not user:
            # Token sai hoặc hết hạn -> Ngắt kết nối với mã 4401 (Unauthorized)
            await websocket.close(code=4401)
            return

        is_member = verify_conversation_member(conversation_id, user.id, db)
        if not is_member:
            # User không phải Buyer hoặc Seller của hội thoại -> Ngắt kết nối với mã 4403 (Forbidden)
            await websocket.close(code=4403)
            return

    # --------------------------------------------------------------------------
    # 2. CHẤP THUẬN KẾT NỐI & VÀO PHÒNG CHAT (AC-10)
    # --------------------------------------------------------------------------
    user_id = user.id
    await manager.connect(conversation_id, websocket, user_id)

    # --------------------------------------------------------------------------
    # 3. VÒNG LẶP TIẾP NHẬN & PHÁT TÁN TIN NHẮN (AC-12)
    # --------------------------------------------------------------------------
    try:
        while True:
            # Nhận dữ liệu text từ Client
            raw_text = await websocket.receive_text()

            # Parse JSON an toàn
            try:
                payload = json.loads(raw_text)
            except Exception:
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Dữ liệu gửi lên phải là định dạng JSON hợp lệ."
                })
                continue

            if not isinstance(payload, dict):
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Payload JSON phải là một Object."
                })
                continue

            action = payload.get("action")

            # ------------------------------------------------------------------
            # SỰ KIỆN 1: GỬI TIN NHẮN MỚI ("send_message")
            # ------------------------------------------------------------------
            if action == "send_message":
                content = str(payload.get("content") or "").strip()
                attachments = payload.get("attachments") or []

                if not content:
                    await manager.send_personal_message(websocket, {
                        "type": "error",
                        "message": "Nội dung tin nhắn không được để trống hoặc chỉ chứa khoảng trắng."
                    })
                    continue

                if len(content) > 2000:
                    await manager.send_personal_message(websocket, {
                        "type": "error",
                        "message": "Nội dung tin nhắn vượt quá giới hạn 2000 ký tự."
                    })
                    continue

                # Lưu DB bằng Session ngắn hạn độc lập (Thread-safe & Pool-safe)
                with SessionLocal() as db:
                    msg_item = save_websocket_message(
                        conversation_id=conversation_id,
                        sender_id=user_id,
                        content=content,
                        attachments=attachments,
                        db=db
                    )

                # Đóng gói sự kiện broadcast chuẩn giao thức AC-12
                event_data = {
                    "type": "new_message",
                    "data": {
                        "message_id": msg_item.message_id,
                        "conversation_id": msg_item.conversation_id,
                        "sender_id": msg_item.sender_id,
                        "content": msg_item.content,
                        "is_read": msg_item.is_read,
                        "sent_at": msg_item.sent_at.isoformat(),
                        "attachments": [
                            {
                                "attachment_id": att.attachment_id,
                                "file_url": att.file_url,
                                "file_type": att.file_type
                            } for att in msg_item.attachments
                        ]
                    }
                }
                # Phát tán tức thời cho toàn bộ người dùng đang online trong phòng chat
                await manager.broadcast_to_room(conversation_id, event_data)

            # ------------------------------------------------------------------
            # SỰ KIỆN 2: BÁO ĐÃ XEM TIN NHẮN ("mark_read")
            # ------------------------------------------------------------------
            elif action == "mark_read":
                with SessionLocal() as db:
                    mark_websocket_messages_as_read(conversation_id, user_id, db)

                now_iso = datetime.now(timezone.utc).isoformat()
                event_data = {
                    "type": "read_receipt",
                    "data": {
                        "conversation_id": conversation_id,
                        "reader_id": user_id,
                        "read_at": now_iso
                    }
                }
                await manager.broadcast_to_room(conversation_id, event_data)

            # ------------------------------------------------------------------
            # SỰ KIỆN 3: HEARTBEAT NHỊP TIM ("ping")
            # ------------------------------------------------------------------
            elif action == "ping":
                await manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            # ------------------------------------------------------------------
            # HÀNH ĐỘNG KHÔNG XÁC ĐỊNH
            # ------------------------------------------------------------------
            else:
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": f"Hành động '{action}' không được hỗ trợ. Các action hợp lệ: 'send_message', 'mark_read', 'ping'."
                })

    except WebSocketDisconnect:
        # Client đóng tab hoặc chủ động ngắt kết nối
        manager.disconnect(conversation_id, websocket, user_id)
    except Exception:
        # Bắt mọi ngoại lệ bất ngờ khác và đảm bảo giải phóng socket
        manager.disconnect(conversation_id, websocket, user_id)


# ==============================================================================
# SELLER REVIEWS & REPUTATION ENDPOINTS (TASK T6: AC-13, AC-14)
# ==============================================================================

@router.post(
    "/product/{product_id}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Đánh giá người bán sau khi giao dịch sản phẩm hoàn tất (AC-13, AC-14)"
)
def submit_product_review(
    product_id: int,
    form: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Gửi đánh giá sao và nhận xét cho người bán sau khi mua hàng:**
    - **Điều kiện**: Tin đăng phải ở trạng thái **'Đã bán' (Sold)**.
    - **Phân quyền**: Người gọi API phải là người mua (`buyer_id`) hoặc người đã từng trao đổi (Conversation) về sản phẩm này.
    - **Ràng buộc**: Không thể tự đánh giá chính mình. Mỗi sản phẩm chỉ được đánh giá duy nhất **1 lần** (AC-14, trả về HTTP 409 nếu trùng).
    - **Hệ quả**: Điểm đánh giá trung bình `rating_avg` của người bán trong bảng `user_stats` tự động được tính toán lại ngay lập tức (AC-13, BR-8).
    """
    return create_review_product(
        user_id=user.id,
        product_id=product_id,
        form=form,
        db=db
    )


@router.get(
    "/product/{product_id}/reviews",
    response_model=List[ReviewResponse],
    status_code=status.HTTP_200_OK,
    summary="Xem danh sách đánh giá của một sản phẩm (Public)"
)
def list_product_reviews(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    **Xem toàn bộ danh sách đánh giá của sản phẩm:**
    - Endpoint công khai (Public), không yêu cầu đăng nhập.
    - Trả về danh sách đánh giá kèm tên và ảnh đại diện của người mua, xếp theo thời gian mới nhất.
    """
    return get_product_reviews(
        product_id=product_id,
        db=db
    )


@router.get(
    "/user/{user_id}/reviews",
    response_model=SellerReviewsResponse,
    status_code=status.HTTP_200_OK,
    summary="Xem điểm uy tín và danh sách nhận xét đánh giá của người bán (Public)"
)
def list_seller_reviews(
    user_id: int,
    page: int = Query(1, ge=1, description="Số trang hiện tại"),
    page_size: int = Query(10, ge=1, le=100, description="Số lượng đánh giá mỗi trang"),
    db: Session = Depends(get_db)
):
    """
    **Xem hồ sơ uy tín và lịch sử đánh giá của người bán:**
    - Endpoint công khai (Public), không yêu cầu đăng nhập.
    - Trả về điểm trung bình `rating_avg` (thang điểm 5, làm tròn 1 số thập phân), tổng số lượt đánh giá `total_reviews`.
    - Hỗ trợ phân trang danh sách nhận xét qua `page` và `page_size`.
    """
    return get_seller_reviews(
        seller_id=user_id,
        page=page,
        page_size=page_size,
        db=db
    )


# ==============================================================================
# 5. POTENTIAL BUYERS, MARK SOLD & NOTIFICATIONS (SEQ 7, 8)
# ==============================================================================

@router.get(
    "/product/{product_id}/potential-buyers",
    response_model=List[PotentialBuyerResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách người đã chat về sản phẩm để chọn người mua khi Đánh dấu Đã bán (Seq 7)"
)
def list_potential_buyers(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phục vụ Popup khi người bán bấm 'Đánh dấu Đã bán' (Seq 7 - Bước 1).
    Chỉ trả về danh sách đối với chính chủ người bán của sản phẩm.
    """
    return get_potential_buyers_for_product(product_id=product_id, seller_id=user.id, db=db)


@router.patch(
    "/product/{product_id}/mark-sold",
    status_code=status.HTTP_200_OK,
    summary="Đánh dấu tin đã bán, chọn người mua và gửi thông báo đánh giá (Seq 7 - Bước 1 & 2)"
)
async def mark_sold_and_request_review(
    product_id: int,
    buyer_id: Optional[int] = Query(None, description="ID người mua được chọn từ danh sách potential-buyers"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Thực hiện trọn vẹn luồng Seq 7:
    - Cập nhật trạng thái tin thành Sold.
    - Tạo Notification mời đánh giá gửi người mua.
    - Push Real-time WebSocket sang cho Người mua để kích hoạt Form đánh giá (Bước 2).
    """
    return await process_mark_sold_and_notify_buyer(
        product_id=product_id,
        seller_id=user.id,
        buyer_id=buyer_id,
        db=db
    )


@router.get(
    "/notifications/me",
    response_model=List[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách thông báo của tôi (Seq 7 Bước 2, Seq 8)"
)
def get_my_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách thông báo để hiển thị danh sách lời mời đánh giá, bình luận, follow (Seq 7, 8).
    """
    return get_user_notifications(user_id=user.id, db=db)


@router.get(
    "/notifications/unread-count",
    status_code=status.HTTP_200_OK,
    summary="Lấy số lượng thông báo chưa đọc để hiển thị Badge count chấm đỏ (Seq 8)"
)
def get_unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Phục vụ render số huy hiệu đỏ trên icon quả chuông thanh Header (Seq 8).
    """
    return get_unread_notifications_count(user_id=user.id, db=db)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Đánh dấu thông báo là đã đọc khi click mở (Seq 7 Bước 2, Seq 8)"
)
def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return mark_notification_as_read(notification_id=notification_id, user_id=user.id, db=db)


@router.patch(
    "/notifications/read-all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Đánh dấu toàn bộ thông báo của tôi là đã đọc (Seq 8)"
)
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return mark_all_notifications_as_read(user_id=user.id, db=db)


# ==============================================================================
# 6. USER FOLLOW / UNFOLLOW TOGGLE & STATUS (SEQ 11)
# ==============================================================================

@router.post(
    "/user/{target_user_id}/follow",
    response_model=FollowToggleResponse,
    status_code=status.HTTP_200_OK,
    summary="Theo dõi hoặc Bỏ theo dõi một người dùng (Follow Toggle - Seq 11)"
)
async def follow_user_endpoint(
    target_user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cơ chế đảo trạng thái theo dõi (Seq 11):
    - Nếu chưa follow -> Bắt đầu theo dõi, tạo Notification và Push WebSocket cho người được follow.
    - Nếu đã follow -> Hủy theo dõi (trả về is_following: false).
    """
    return await toggle_follow_user(follower_id=user.id, followed_id=target_user_id, db=db)


@router.get(
    "/user/{target_user_id}/follow-status",
    response_model=FollowStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Kiểm tra trạng thái theo dõi và tổng số lượt followers/following"
)
def get_follow_status_endpoint(
    target_user_id: int,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Kiểm tra trạng thái follow khi truy cập trang cá nhân của người bán (Seq 11).
    """
    current_uid = user.id if user else None
    return check_follow_status(current_user_id=current_uid, target_user_id=target_user_id, db=db)


# ==============================================================================
# 7. GLOBAL NOTIFICATION WEBSOCKET ENDPOINT (TASK T8: TOÀN BỘ SỰ KIỆN REAL-TIME)
# ==============================================================================

@router.websocket("/ws/notifications")
async def websocket_notifications_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT Bearer Token truyền qua Query Param")
):
    """
    Kênh WebSocket tiếp nhận thông báo thời gian thực toàn sàn UniMarket (Task T8).
    - URL kết nối: ws://localhost:8000/interaction/ws/notifications?token={jwt_token}
    - Mục đích:
      + Nhận thông báo nảy chuông khi có bình luận mới về bài đăng của mình.
      + Nhận thông báo khi có người trả lời bình luận của mình.
      + Nhận thông báo khi có người theo dõi gian hàng của mình.
      + Nhận thông báo khi tin đăng được duyệt, hoặc đơn hàng đổi trạng thái.
    - Cơ chế bảo mật:
      + Đóng kết nối mã 4401 (Unauthorized) nếu thiếu token, sai token hoặc token hết hạn.
      + Sử dụng DB Session ngắn hạn (Short-lived) trong quá trình handshake để không chiếm pool.
    - Cơ chế giao tiếp:
      + Client -> Server: {"action": "ping"} (Heartbeat) hoặc {"type": "ping"}
      + Client -> Server: {"action": "mark_read", "notification_id": 123}
      + Client -> Server: {"action": "mark_read_all"}
      + Server -> Client: {"type": "new_notification", "data": {...}}
      + Server -> Client: {"type": "pong", "timestamp": "..."}
    """
    # --------------------------------------------------------------------------
    # 1. BẢO MẬT & XÁC THỰC HANDSHAKE
    # --------------------------------------------------------------------------
    with SessionLocal() as db:
        user = authenticate_ws_token(token, db)
        if not user:
            # Token không hợp lệ -> Đóng kết nối với mã RFC 4401
            await websocket.close(code=4401)
            return

    user_id = user.id

    # --------------------------------------------------------------------------
    # 2. CHẤP THUẬN KẾT NỐI VÀ ĐĂNG KÝ VÀO CONNECTION MANAGER
    # --------------------------------------------------------------------------
    await manager.connect_user_notifications(websocket, user_id)

    # --------------------------------------------------------------------------
    # 3. VÒNG LẶP LẮNG NGHE TIMEOUT & TIN NHẮN TỪ CLIENT
    # --------------------------------------------------------------------------
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                payload = json.loads(raw_text)
            except Exception:
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Dữ liệu gửi lên phải là định dạng JSON hợp lệ."
                })
                continue

            if not isinstance(payload, dict):
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Payload JSON phải là một Object."
                })
                continue

            action = payload.get("action") or payload.get("type")

            # Xử lý Heartbeat Ping từ Client
            if action == "ping":
                await manager.send_personal_message(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

            # Xử lý Đánh dấu đã đọc thông báo qua WebSocket
            elif action == "mark_read":
                noti_id = payload.get("notification_id")
                if noti_id and isinstance(noti_id, int):
                    with SessionLocal() as db:
                        try:
                            mark_notification_as_read(notification_id=noti_id, user_id=user_id, db=db)
                            await manager.send_personal_message(websocket, {
                                "type": "notification_read_ack",
                                "notification_id": noti_id
                            })
                        except Exception:
                            pass

            elif action == "mark_read_all":
                with SessionLocal() as db:
                    try:
                        mark_all_notifications_as_read(user_id=user_id, db=db)
                        await manager.send_personal_message(websocket, {
                            "type": "notification_read_all_ack"
                        })
                    except Exception:
                        pass

    except WebSocketDisconnect:
        # Client chủ động đóng tab hoặc mất mạng bình thường
        manager.disconnect_user_notifications(websocket, user_id)
    except Exception:
        # Ngoại lệ bất ngờ
        manager.disconnect_user_notifications(websocket, user_id)


