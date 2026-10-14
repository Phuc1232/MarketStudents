from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from src.api.deps import get_db
from src.modules.User.service import get_current_user
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
    send_message_rest
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