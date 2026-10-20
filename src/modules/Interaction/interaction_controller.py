from fastapi import APIRouter, Depends, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional, List
import json
from datetime import datetime, timezone
from src.Core.database import SessionLocal
from src.api.deps import get_db
from src.modules.User.service import get_current_user
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
    MessageResponse
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
    mark_websocket_messages_as_read
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
    summary="Đăng bình luận mới hoặc phản hồi câu hỏi dưới bài đăng (AC-4, AC-5)"
)
def post_comment(
    product_id: int,
    form: CommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    - **AC-4**: Nếu `parent_id = None` -> Tạo bình luận gốc mới.
    - **AC-5**: Nếu truyền `parent_id` hợp lệ -> Tạo câu trả lời (Reply).
    - Tự động chuẩn hóa độ sâu tối đa 2 cấp (BR-2).
    """
    return create_product_comment(
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