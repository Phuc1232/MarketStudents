from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ==============================================================================
# 0. COMMON & EMBEDDED SUMMARY SCHEMAS
# ==============================================================================
class MessageResponse(BaseModel):
    message: str


class UserSummaryResponse(BaseModel):
    user_id: int
    full_name: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProductSummaryResponse(BaseModel):
    product_id: int
    title: str
    price: float
    thumbnail_url: Optional[str] = None
    seller_id: int
    status_id: int

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 1. WISHLIST / FAVORITES SCHEMAS (AC-1, AC-2, AC-3)
# ==============================================================================
class FavoriteToggleResponse(BaseModel):
    product_id: int
    is_favorited: bool
    message: str
    total_favorites: int


class FavoriteStatusResponse(BaseModel):
    product_id: int
    is_favorited: bool


class FavoriteProductItemResponse(BaseModel):
    product_id: int
    title: str
    price: float
    thumbnail_url: Optional[str] = None
    condition_name: Optional[str] = None
    seller_id: int
    seller_name: str
    seller_avatar: Optional[str] = None
    status_id: int
    favorited_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedFavoritesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[FavoriteProductItemResponse]


# ==============================================================================
# 2. NESTED COMMENTS SCHEMAS (AC-4, AC-5, AC-6, AC-7)
# ==============================================================================
class CommentAuthorResponse(BaseModel):
    user_id: int
    full_name: str
    avatar_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000, description="Nội dung bình luận (1-1000 ký tự)")
    parent_id: Optional[int] = Field(None, description="ID bình luận gốc nếu là phản hồi (reply)")


class CommentItemResponse(BaseModel):
    comment_id: int
    product_id: int
    content: str
    parent_id: Optional[int] = None
    author: CommentAuthorResponse
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CommentTreeResponse(BaseModel):
    comment_id: int
    product_id: int
    content: str
    author: CommentAuthorResponse
    created_at: datetime
    replies: List[CommentItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. REAL-TIME CHAT & CONVERSATION SCHEMAS (AC-8, AC-9, AC-10, AC-12)
# ==============================================================================
class ConversationCreate(BaseModel):
    product_id: int = Field(..., description="ID sản phẩm cần trao đổi với người bán")


class ConversationPartnerResponse(BaseModel):
    user_id: int
    full_name: str
    avatar_url: Optional[str] = None
    rating_avg: Optional[float] = 0.0

    model_config = ConfigDict(from_attributes=True)


class MessageAttachmentResponse(BaseModel):
    attachment_id: int
    file_url: str
    file_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="Nội dung tin nhắn")
    attachments: Optional[List[str]] = Field(default=None, description="Danh sách URL hình ảnh đính kèm (nếu có)")


class MessageResponseItem(BaseModel):
    message_id: int
    conversation_id: int
    sender_id: int
    content: str
    is_read: bool
    sent_at: datetime
    attachments: List[MessageAttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ConversationListItemResponse(BaseModel):
    conversation_id: int
    product: ProductSummaryResponse
    partner: ConversationPartnerResponse
    last_message: Optional[MessageResponseItem] = None
    unread_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    conversation_id: int
    product: ProductSummaryResponse
    partner: ConversationPartnerResponse
    last_message_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedMessagesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[MessageResponseItem]


# ==============================================================================
# 4. REVIEWS & SELLER REPUTATION SCHEMAS (AC-13, AC-14)
# ==============================================================================
class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Điểm đánh giá từ 1 đến 5 sao")
    content: Optional[str] = Field(None, max_length=1000, description="Nhận xét chi tiết về người bán và giao dịch")


class ReviewResponse(BaseModel):
    product_id: int
    reviewer: UserSummaryResponse
    reviewee_id: int
    rating: int
    content: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SellerReviewsResponse(BaseModel):
    seller_id: int
    rating_avg: float = Field(..., description="Điểm đánh giá trung bình làm tròn 1 chữ số thập phân (vd: 4.8)")
    total_reviews: int = Field(..., description="Tổng số lượt đánh giá người bán đã nhận")
    page: Optional[int] = Field(1, description="Số trang hiện tại")
    page_size: Optional[int] = Field(10, description="Số lượng đánh giá trên mỗi trang")
    reviews: List[ReviewResponse] = Field(default=[], description="Danh sách các đánh giá nhận được")

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. WEBSOCKET REAL-TIME CHAT SCHEMAS (TASK T5: AC-10, AC-11, AC-12)
# ==============================================================================

class WSIncomingPayload(BaseModel):
    """Payload dữ liệu Client gửi lên Server qua kết nối WebSocket"""
    action: str = Field(..., description="Hành động: 'send_message', 'mark_read', 'ping'")
    content: Optional[str] = Field(None, min_length=1, max_length=2000, description="Nội dung tin nhắn")
    attachments: Optional[List[str]] = Field(default=None, description="Danh sách URL hình ảnh đính kèm")


class WSNewMessageData(BaseModel):
    message_id: int
    conversation_id: int
    sender_id: int
    content: str
    is_read: bool
    sent_at: datetime
    attachments: List[MessageAttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class WSNewMessageEvent(BaseModel):
    type: str = "new_message"
    data: WSNewMessageData


class WSReadReceiptData(BaseModel):
    conversation_id: int
    reader_id: int
    read_at: datetime


class WSReadReceiptEvent(BaseModel):
    type: str = "read_receipt"
    data: WSReadReceiptData


class WSPongEvent(BaseModel):
    type: str = "pong"
    timestamp: datetime


class WSErrorEvent(BaseModel):
    type: str = "error"
    message: str


# ==============================================================================
# 6. POTENTIAL BUYERS, FOLLOW & NOTIFICATIONS SCHEMAS (SEQ 7, 8, 11)
# ==============================================================================

class PotentialBuyerResponse(BaseModel):
    user_id: int
    full_name: str
    avatar_url: Optional[str] = None
    conversation_id: int
    last_message_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FollowToggleResponse(BaseModel):
    followed_id: int
    is_following: bool
    message: str
    total_followers: int


class FollowStatusResponse(BaseModel):
    user_id: int
    is_following: bool
    total_followers: int
    total_following: int


class NotificationResponse(BaseModel):
    notification_id: int
    user_id: int
    title: str
    message: Optional[str] = None
    action_link: Optional[str] = None
    is_read: bool

    model_config = ConfigDict(from_attributes=True)