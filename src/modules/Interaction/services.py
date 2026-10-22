from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, or_, update
from fastapi import HTTPException, status
from typing import Optional, List, Dict
from datetime import datetime, timezone
from src.share.uilts import SECRET_KEY, ALGORITHM, jwt
from src.modules import (
    FavoriteToggleResponse,
    FavoriteStatusResponse,
    FavoriteProductItemResponse,
    PaginatedFavoritesResponse,
    Product, ProductImage, ProductCondition,
    Favorite,
    User, userProfile, userStats,
    Conversation, Participation, Message, MessageAttachment,
    Comment,
    CommentAuthorResponse, CommentCreate, CommentItemResponse, CommentTreeResponse,
    ConversationCreate, ConversationDetailResponse, ConversationListItemResponse,
    ConversationPartnerResponse, MessageAttachmentResponse, MessageResponseItem,
    MessageCreate, PaginatedMessagesResponse, ProductSummaryResponse, MessageResponse,
    ReviewProductConversation, ReviewCreate, ReviewResponse, SellerReviewsResponse, UserSummaryResponse,
    Follow, Notification,
    PotentialBuyerResponse, FollowToggleResponse, FollowStatusResponse, NotificationResponse,
    Report, ReportReason, ReportReasonResponse, ReportCreate, ReportResponse, UserReportHistoryItem,
    FollowUserItemResponse, PaginatedFollowersResponse,
    manager
)

def get_user_display_name (user: Optional[User]):
    if not user:
        return "Người dùng ẩn danh"
    if user.profile:
        full = f"{user.profile.last_name or ''} {user.profile.first_name or ''}".strip()
        if full:
            return full
    if user.Email:
        return user.Email.split("@")[0]
    return f"User #{user.id}"

def get_user_avatar(user: Optional[User]) -> Optional[str]:
    """Trả về URL ảnh đại diện của người dùng nếu có."""
    if user and user.profile and user.profile.avatar_url:
        return user.profile.avatar_url
    return None

def get_product_thumbnails (product: Product):
    if product.thumbnails:
        return product.thumbnails
    if product.images:
        for img in product.images:
            if getattr(img, 'is_thumbnail', False) or getattr(img, 'is_thumnail', False):
                return img.image_url
        return product.images[0].image_url
    return None

def toggle_favorite_product (user_id: int, product_id: int, db: Session):
    stmt = select(Product).where(Product.product_id == product_id, Product.deleted_at == None)
    product = db.scalars(stmt).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm ID {product_id} không tồn tại hoặc đã bị xóa."
        )
    if product.seller_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự thả tim tin đăng của chính mình."
        )
    exsiting_favorite = db.get(Favorite, (user_id,product_id))
    if exsiting_favorite:
        db.delete(exsiting_favorite)
        db.commit()
        is_favorite = False
        Message = "Đã xoá sản phẩm khỏi mục yêu thích"
    else:
        favorites = Favorite(user_id = user_id, product_id = product_id)
        db.add(favorites)
        db.commit()
        is_favorite = True
        Message = "Đã thêm sản phẩm vào mục yêu thích"
    stmt = select(func.count()).select_from(Favorite).where(Favorite.product_id == product_id)
    total_fav = db.scalar(stmt) or 0
    return FavoriteToggleResponse(
        product_id= product_id,
        is_favorited= is_favorite,
        message= Message,
        total_favorites=total_fav
    )

def get_user_favorite (user_id: int, page: int=1, page_size: int =20, db: Session=None):
    offset = (page-1)*page_size
    stmt = select(func.count()).select_from(Favorite)\
                    .join(Product, Product.product_id == Favorite.product_id)\
                    .where(Favorite.user_id == user_id,Product.deleted_at == None)
    total = db.scalar(stmt) or 0

    stmt = select(Favorite,Product).join(Product, Product.product_id == Favorite.product_id)\
                        .options(selectinload(Product.seller).selectinload(User.profile),
                                 selectinload(Product.condition),
                                 selectinload(Product.images))\
                        .where(
                            Favorite.user_id == user_id,
                            Product.deleted_at == None
                        ).offset(offset).limit(page_size)
    result = db.execute(stmt).all()
    items : List[FavoriteProductItemResponse] = []
    for fav,pro in result:
        thumb = get_product_thumbnails(pro)
        condition_name = pro.condition.condition_name if pro.condition else None
        seller_name = get_user_display_name(pro.seller)
        seller_avatar = get_user_avatar(pro.seller)

        items.append(
            FavoriteProductItemResponse(
                product_id=pro.product_id,
                title=pro.title,
                price=pro.price,
                thumbnail_url=thumb,
                condition_name=condition_name,
                seller_id=pro.seller_id,
                seller_name=seller_name,
                seller_avatar=seller_avatar,
                status_id=pro.status_id,
                favorited_at=fav.created_at or datetime.now()
            )
        )
    return PaginatedFavoritesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )

def check_favorite_status (user_id: int, product_id: int, db: Session):
    favorite = db.get(Favorite, (user_id, product_id))
    if favorite is not None:
        return FavoriteStatusResponse(
            product_id=product_id,
            is_favorited=True
        )
    return None


# ==============================================================================
# TASK T3: PHÂN HỆ BÌNH LUẬN ĐA CẤP (NESTED COMMENTS: AC-4, AC-5, AC-6, AC-7)
# ==============================================================================

async def create_product_comment(
    user_id: int,
    product_id: int,
    form: CommentCreate,
    db: Session
) -> CommentItemResponse:
    """
    Tạo bình luận mới cho sản phẩm (Bình luận gốc hoặc Phản hồi reply).
    - BR-2: Nội dung từ 1 đến 1000 ký tự.
    - parent_id phải trỏ tới một comment hợp lệ của cùng sản phẩm.
    - Giới hạn độ sâu 2 cấp: Nếu reply vào một comment con cấp 2, hệ thống tự động
      gán parent_id trỏ về comment gốc để giữ giao diện phẳng 2 tầng.
    - Tự động tạo Notification và Push Real-time (Seq 16 Giai đoạn 1 & 3).
    - Covers: AC-4, AC-5
    """
    # 1. Kiểm tra sản phẩm tồn tại và chưa bị xóa mềm
    stmt_prod = select(Product).where(
        Product.product_id == product_id,
        Product.deleted_at.is_(None)
    )
    product = db.scalars(stmt_prod).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm ID {product_id} không tồn tại hoặc đã bị xóa."
        )

    # 2. Kiểm tra nội dung bình luận
    content_clean = form.content.strip()
    if not content_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nội dung bình luận không được để trống hoặc chỉ chứa khoảng trắng."
        )

    # 3. Xử lý parent_id (Logic phân cấp 2 tầng theo BR-2)
    final_parent_id: Optional[int] = None
    target_parent_comment: Optional[Comment] = None

    if form.parent_id is not None:
        parent_comment = db.get(Comment, form.parent_id)
        if not parent_comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bình luận gốc ID {form.parent_id} không tồn tại."
            )

        if parent_comment.product_id != product_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bình luận phản hồi không thuộc về cùng một sản phẩm."
            )

        target_parent_comment = parent_comment
        # Nếu bình luận cha đã là reply cấp 2 (đã có parent_id), thì gán parent_id về comment gốc
        if parent_comment.parent_id is not None:
            final_parent_id = parent_comment.parent_id
        else:
            final_parent_id = parent_comment.comment_id

    # 4. Tạo bản ghi bình luận mới
    new_comment = Comment(
        product_id=product_id,
        user_id=user_id,
        content=content_clean,
        parent_id=final_parent_id
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # 5. Nạp thông tin tác giả bình luận
    author_user = db.scalars(
        select(User).options(selectinload(User.profile)).where(User.id == user_id)
    ).first()

    author_dto = CommentAuthorResponse(
        user_id=user_id,
        full_name=get_user_display_name(author_user),
        avatar_url=get_user_avatar(author_user)
    )

    created_time = getattr(new_comment, 'CreatedAt', getattr(new_comment, 'created_at', datetime.now(timezone.utc)))
    updated_time = getattr(new_comment, 'UpdateAt', getattr(new_comment, 'updated_at', None))

    # 6. Tạo Notification và Push Real-time theo Sequence 16
    author_name = get_user_display_name(author_user)
    noti_target_user_id = None
    noti_title = ""
    noti_msg = ""

    if final_parent_id is None:
        # Giai đoạn 1 (Seq 16): Bình luận gốc -> Báo cho Người bán (chủ tin đăng)
        if user_id != product.seller_id:
            noti_target_user_id = product.seller_id
            noti_title = "Có bình luận mới về sản phẩm"
            noti_msg = f"{author_name} đã bình luận về sản phẩm '{product.title}' của bạn: \"{content_clean[:60]}\""
    else:
        # Giai đoạn 3 (Seq 16): Phản hồi -> Báo cho tác giả của bình luận gốc
        if target_parent_comment and target_parent_comment.user_id != user_id:
            noti_target_user_id = target_parent_comment.user_id
            if user_id == product.seller_id:
                noti_title = "Người bán đã trả lời bình luận"
                noti_msg = f"Người bán đã trả lời bình luận của bạn trên sản phẩm '{product.title}': \"{content_clean[:60]}\""
            else:
                noti_title = "Có phản hồi mới về bình luận"
                noti_msg = f"{author_name} đã trả lời bình luận của bạn trên sản phẩm '{product.title}': \"{content_clean[:60]}\""

    if noti_target_user_id:
        new_noti = Notification(
            user_id=noti_target_user_id,
            title=noti_title,
            message=noti_msg,
            action_link=f"/product/{product_id}",
            is_read=False
        )
        db.add(new_noti)
        db.commit()
        db.refresh(new_noti)

        try:
            await manager.send_to_user(noti_target_user_id, {
                "type": "new_notification",
                "data": {
                    "notification_id": new_noti.notification_id,
                    "title": new_noti.title,
                    "message": new_noti.message,
                    "action_link": new_noti.action_link,
                    "is_read": False,
                    "tag": "new_comment",
                    "product_id": product_id
                }
            })
        except Exception:
            pass

    return CommentItemResponse(
        comment_id=new_comment.comment_id,
        product_id=new_comment.product_id,
        content=new_comment.content,
        parent_id=new_comment.parent_id,
        author=author_dto,
        created_at=created_time,
        updated_at=updated_time
    )


def get_product_comments_tree(
    product_id: int,
    db: Session
) -> List[CommentTreeResponse]:
    """
    Lấy danh sách bình luận của sản phẩm theo cấu trúc cây 2 tầng (Nested Tree).
    - Cấp 1: Bình luận gốc (parent_id is None).
    - Cấp 2: Danh sách replies con nằm trong field `replies` của mỗi bình luận gốc.
    - Sắp xếp theo thứ tự thời gian tăng dần để người dùng dễ theo dõi cuộc trò chuyện.
    - Covers: AC-6
    """
    # 1. Kiểm tra sản phẩm tồn tại
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm ID {product_id} không tồn tại hoặc đã bị xóa."
        )

    # 2. Truy vấn toàn bộ bình luận của sản phẩm kèm thông tin người dùng và hồ sơ
    stmt = (
        select(Comment)
        .options(
            selectinload(Comment.user).selectinload(User.profile)
        )
        .where(Comment.product_id == product_id)
        .order_by(Comment.comment_id.asc())
    )
    all_comments = db.scalars(stmt).all()

    # 3. Thuật toán gom nhóm phân cấp (Tree grouping)
    root_comments: List[Comment] = []
    replies_map: Dict[int, List[CommentItemResponse]] = {}

    for c in all_comments:
        author_dto = CommentAuthorResponse(
            user_id=c.user.id if c.user else c.user_id,
            full_name=get_user_display_name(c.user),
            avatar_url=get_user_avatar(c.user)
        )
        created_time = getattr(c, 'CreatedAt', getattr(c, 'created_at', datetime.now(timezone.utc)))
        updated_time = getattr(c, 'UpdateAt', getattr(c, 'updated_at', None))

        item_dto = CommentItemResponse(
            comment_id=c.comment_id,
            product_id=c.product_id,
            content=c.content,
            parent_id=c.parent_id,
            author=author_dto,
            created_at=created_time,
            updated_at=updated_time
        )

        if c.parent_id is None:
            root_comments.append(c)
        else:
            if c.parent_id not in replies_map:
                replies_map[c.parent_id] = []
            replies_map[c.parent_id].append(item_dto)

    # 4. Đóng gói danh sách cây bình luận hoàn chỉnh
    tree_result: List[CommentTreeResponse] = []
    for root in root_comments:
        root_author = CommentAuthorResponse(
            user_id=root.user.id if root.user else root.user_id,
            full_name=get_user_display_name(root.user),
            avatar_url=get_user_avatar(root.user)
        )
        root_created = getattr(root, 'CreatedAt', getattr(root, 'created_at', datetime.now(timezone.utc)))

        tree_result.append(
            CommentTreeResponse(
                comment_id=root.comment_id,
                product_id=root.product_id,
                content=root.content,
                author=root_author,
                created_at=root_created,
                replies=replies_map.get(root.comment_id, [])
            )
        )

    return tree_result


def delete_comment(
    comment_id: int,
    user_id: int,
    db: Session
) -> MessageResponse:
    """
    Xóa bình luận khỏi hệ thống.
    - BR-3: Chỉ cho phép người viết bình luận HOẶC chủ tin đăng (người bán) xóa bình luận.
    - Xóa kèm toàn bộ các bình luận con (replies) để tránh vi phạm khóa ngoại tự tham chiếu.
    - Covers: AC-7
    """
    # 1. Tìm bình luận cần xóa kèm thông tin sản phẩm sở hữu
    stmt = (
        select(Comment)
        .options(selectinload(Comment.product))
        .where(Comment.comment_id == comment_id)
    )
    comment = db.scalars(stmt).first()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bình luận ID {comment_id} không tồn tại."
        )

    # 2. Kiểm tra thẩm quyền xóa (Người viết HOẶC Chủ tin đăng)
    is_author = (comment.user_id == user_id)
    is_product_owner = (comment.product and comment.product.seller_id == user_id)

    if not (is_author or is_product_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền xóa bình luận này. Chỉ tác giả bình luận hoặc chủ bài đăng mới được phép xóa."
        )

    # 3. Xóa các bình luận phản hồi con (nếu có) trước để tránh lỗi Foreign Key
    stmt_replies = select(Comment).where(Comment.parent_id == comment_id)
    child_replies = db.scalars(stmt_replies).all()
    for child in child_replies:
        db.delete(child)

    # 4. Xóa bình luận chính
    db.delete(comment)
    db.commit()

    return MessageResponse(
        message="Đã xóa bình luận thành công."
    )


# ==============================================================================
# TASK T4: QUẢN LÝ HỘI THOẠI & LỊCH SỬ TIN NHẮN (CHAT REST API)
# ==============================================================================

def get_or_create_conversation(
    buyer_id: int,
    form: ConversationCreate,
    db: Session
) -> ConversationDetailResponse:
    """
    Tìm hoặc tạo mới một cuộc hội thoại gắn liền với sản phẩm giữa Buyer và Seller.
    - BR-4: Mỗi sản phẩm chỉ có duy nhất 1 cuộc hội thoại giữa 1 Buyer và 1 Seller.
    - Người bán không thể tự chat với chính mình trên tin đăng của mình.
    - Covers: AC-8
    """
    # 1. Kiểm tra sản phẩm tồn tại và chưa bị xóa mềm
    stmt_prod = select(Product).options(
        selectinload(Product.seller).selectinload(User.profile),
        selectinload(Product.seller).selectinload(User.stats),
        selectinload(Product.images)
    ).where(
        Product.product_id == form.product_id,
        Product.deleted_at.is_(None)
    )
    product = db.scalars(stmt_prod).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm ID {form.product_id} không tồn tại hoặc đã bị xóa."
        )

    # 2. Không cho phép tự chat với bản thân
    if product.seller_id == buyer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự tạo cuộc hội thoại trò chuyện với chính mình về sản phẩm của bạn."
        )

    seller = product.seller

    # 3. Tìm xem cuộc hội thoại cho sản phẩm này giữa Buyer và Seller đã tồn tại chưa
    stmt_conv = (
        select(Conversation)
        .join(Participation, Conversation.conversation_id == Participation.conversation_id)
        .where(
            Conversation.product_id == form.product_id,
            Participation.buyer_id == buyer_id,
            Participation.seller_id == product.seller_id
        )
    )
    conversation = db.scalars(stmt_conv).first()

    # 4. Nếu chưa có -> Tạo mới Conversation và Participation
    if not conversation:
        now_time = datetime.now(timezone.utc)
        conversation = Conversation(
            product_id=form.product_id,
            last_message_at=now_time
        )
        db.add(conversation)
        db.flush()  # Lấy conversation_id tự sinh

        participation = Participation(
            buyer_id=buyer_id,
            seller_id=product.seller_id,
            conversation_id=conversation.conversation_id
        )
        db.add(participation)
        db.commit()
        db.refresh(conversation)

    # 5. Đóng gói DTO phản hồi
    seller_rating = seller.stats.rating_avg if (seller and seller.stats) else 0.0
    partner_dto = ConversationPartnerResponse(
        user_id=seller.id,
        full_name=get_user_display_name(seller),
        avatar_url=get_user_avatar(seller),
        rating_avg=seller_rating
    )

    product_dto = ProductSummaryResponse(
        product_id=product.product_id,
        title=product.title,
        price=product.price,
        thumbnail_url=get_product_thumbnails(product),
        seller_id=product.seller_id,
        status_id=product.status_id
    )

    return ConversationDetailResponse(
        conversation_id=conversation.conversation_id,
        product=product_dto,
        partner=partner_dto,
        last_message_at=conversation.last_message_at
    )


def get_my_conversations(
    user_id: int,
    db: Session
) -> List[ConversationListItemResponse]:
    """
    Lấy danh sách các cuộc hội thoại (Hộp thư đến / Inbox) mà người dùng hiện tại tham gia.
    - Sắp xếp theo tin nhắn mới nhất (last_message_at giảm dần).
    - Tự động nhận diện đối tác trò chuyện (người mua hoặc người bán).
    - Tính toán số lượng tin nhắn chưa đọc từ đối tác gửi tới.
    - Covers: AC-9
    """
    # 1. Truy vấn các hội thoại kèm thông tin đối tác và sản phẩm
    stmt = (
        select(Conversation, Participation)
        .join(Participation, Conversation.conversation_id == Participation.conversation_id)
        .options(
            selectinload(Conversation.product).selectinload(Product.images),
            selectinload(Participation.buyer).selectinload(User.profile),
            selectinload(Participation.buyer).selectinload(User.stats),
            selectinload(Participation.seller).selectinload(User.profile),
            selectinload(Participation.seller).selectinload(User.stats)
        )
        .where(
            or_(
                Participation.buyer_id == user_id,
                Participation.seller_id == user_id
            )
        )
        .order_by(Conversation.last_message_at.desc().nulls_last())
    )

    results = db.execute(stmt).all()
    inbox_items: List[ConversationListItemResponse] = []

    for conv, part in results:
        # Xác định ai là đối tác (partner) của user hiện tại
        if user_id == part.buyer_id:
            partner_user = part.seller
        else:
            partner_user = part.buyer

        partner_rating = partner_user.stats.rating_avg if (partner_user and partner_user.stats) else 0.0
        partner_dto = ConversationPartnerResponse(
            user_id=partner_user.id,
            full_name=get_user_display_name(partner_user),
            avatar_url=get_user_avatar(partner_user),
            rating_avg=partner_rating
        )

        # Lấy thông tin sản phẩm tóm tắt
        prod = conv.product
        product_dto = ProductSummaryResponse(
            product_id=prod.product_id if prod else 0,
            title=prod.title if prod else "Sản phẩm không khả dụng",
            price=prod.price if prod else 0.0,
            thumbnail_url=get_product_thumbnails(prod) if prod else None,
            seller_id=prod.seller_id if prod else 0,
            status_id=prod.status_id if prod else 0
        )

        # Lấy tin nhắn mới nhất trong hội thoại này
        stmt_last_msg = (
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.conversation_id == conv.conversation_id)
            .order_by(Message.sent_at.desc())
            .limit(1)
        )
        last_msg = db.scalars(stmt_last_msg).first()

        last_msg_dto = None
        if last_msg:
            attachments_dto = [
                MessageAttachmentResponse(
                    attachment_id=att.attachment_id,
                    file_url=att.file_url,
                    file_type=att.file_type
                ) for att in last_msg.attachments
            ]
            last_msg_dto = MessageResponseItem(
                message_id=last_msg.message_id,
                conversation_id=last_msg.conversation_id,
                sender_id=last_msg.sender_id,
                content=last_msg.content,
                is_read=last_msg.is_read,
                sent_at=last_msg.sent_at,
                attachments=attachments_dto
            )

        # Đếm số tin nhắn chưa đọc mà đối phương gửi cho user hiện tại
        stmt_unread = (
            select(func.count())
            .select_from(Message)
            .where(
                Message.conversation_id == conv.conversation_id,
                Message.sender_id != user_id,
                Message.is_read == False
            )
        )
        unread_count = db.scalar(stmt_unread) or 0

        inbox_items.append(
            ConversationListItemResponse(
                conversation_id=conv.conversation_id,
                product=product_dto,
                partner=partner_dto,
                last_message=last_msg_dto,
                unread_count=unread_count
            )
        )

    return inbox_items


def get_conversation_messages(
    conversation_id: int,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = None
) -> PaginatedMessagesResponse:
    """
    Lấy danh sách lịch sử tin nhắn trong một cuộc hội thoại có phân trang.
    - Bảo mật: Bắt buộc kiểm tra quyền tham gia (user_id phải là Buyer hoặc Seller).
    - Sắp xếp tin nhắn theo thứ tự thời gian gửi (sent_at tăng dần) để render luồng chat.
    - Covers: AC-9
    """
    # 1. Kiểm tra quyền truy cập hội thoại (Authorization check)
    stmt_part = select(Participation).where(
        Participation.conversation_id == conversation_id,
        or_(
            Participation.buyer_id == user_id,
            Participation.seller_id == user_id
        )
    )
    part = db.scalars(stmt_part).first()

    if not part:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập vào cuộc hội thoại này."
        )

    # 2. Đếm tổng số tin nhắn trong cuộc hội thoại
    stmt_count = (
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id)
    )
    total = db.scalar(stmt_count) or 0

    # 3. Phân trang lấy danh sách tin nhắn
    offset = (page - 1) * page_size
    stmt_msgs = (
        select(Message)
        .options(selectinload(Message.attachments))
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sent_at.asc())
        .offset(offset)
        .limit(page_size)
    )
    messages = db.scalars(stmt_msgs).all()

    # 4. Map dữ liệu sang Pydantic DTO
    items: List[MessageResponseItem] = []
    for m in messages:
        att_dtos = [
            MessageAttachmentResponse(
                attachment_id=a.attachment_id,
                file_url=a.file_url,
                file_type=a.file_type
            ) for a in m.attachments
        ]
        items.append(
            MessageResponseItem(
                message_id=m.message_id,
                conversation_id=m.conversation_id,
                sender_id=m.sender_id,
                content=m.content,
                is_read=m.is_read,
                sent_at=m.sent_at,
                attachments=att_dtos
            )
        )

    return PaginatedMessagesResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def mark_messages_as_read(
    conversation_id: int,
    user_id: int,
    db: Session
) -> MessageResponse:
    """
    Đánh dấu tất cả tin nhắn đối phương gửi trong hội thoại này thành đã đọc (is_read = True).
    - Cập nhật khi người dùng mở xem hộp chat.
    - Covers: BR-6
    """
    # 1. Kiểm tra quyền sở hữu hội thoại
    stmt_part = select(Participation).where(
        Participation.conversation_id == conversation_id,
        or_(
            Participation.buyer_id == user_id,
            Participation.seller_id == user_id
        )
    )
    part = db.scalars(stmt_part).first()

    if not part:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thao tác trên cuộc hội thoại này."
        )

    # 2. Cập nhật tất cả tin nhắn do đối phương gửi (sender_id != user_id)
    stmt_update = (
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.is_read == False
        )
        .values(is_read=True)
    )
    db.execute(stmt_update)
    db.commit()

    return MessageResponse(
        message="Đã cập nhật trạng thái đã đọc cho toàn bộ tin nhắn trong hội thoại."
    )


def send_message_rest(
    conversation_id: int,
    user_id: int,
    form: MessageCreate,
    db: Session = None
) -> MessageResponseItem:
    """
    Gửi tin nhắn văn bản và tệp đính kèm vào cuộc hội thoại qua giao thức HTTP REST.
    - Tự động cập nhật thời gian last_message_at của Conversation.
    - covers: AC-8, AC-9
    """
    # 1. Kiểm tra quyền tham gia hội thoại
    stmt_part = select(Participation).where(
        Participation.conversation_id == conversation_id,
        or_(
            Participation.buyer_id == user_id,
            Participation.seller_id == user_id
        )
    )
    part = db.scalars(stmt_part).first()

    if not part:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền gửi tin nhắn trong cuộc hội thoại này."
        )

    # 2. Tạo bản ghi tin nhắn mới
    now_time = datetime.now(timezone.utc)
    new_msg = Message(
        conversation_id=conversation_id,
        sender_id=user_id,
        content=form.content.strip(),
        is_read=False,
        sent_at=now_time
    )
    db.add(new_msg)
    db.flush()

    # 3. Thêm các ảnh đính kèm (nếu có)
    att_dtos: List[MessageAttachmentResponse] = []
    if form.attachments:
        for url in form.attachments:
            new_att = MessageAttachment(
                message_id=new_msg.message_id,
                file_url=url,
                file_type="image"
            )
            db.add(new_att)
            db.flush()
            att_dtos.append(
                MessageAttachmentResponse(
                    attachment_id=new_att.attachment_id,
                    file_url=new_att.file_url,
                    file_type=new_att.file_type
                )
            )

    # 4. Cập nhật thời gian tin nhắn cuối cùng của Conversation
    conv = db.get(Conversation, conversation_id)
    if conv:
        conv.last_message_at = now_time

    db.commit()
    db.refresh(new_msg)

    return MessageResponseItem(
        message_id=new_msg.message_id,
        conversation_id=new_msg.conversation_id,
        sender_id=new_msg.sender_id,
        content=new_msg.content,
        is_read=new_msg.is_read,
        sent_at=new_msg.sent_at,
        attachments=att_dtos
    )


# ==============================================================================
# TASK T5: NGHIỆP VỤ XỬ LÝ CHO KÊNH WEBSOCKET REAL-TIME CHAT
# ==============================================================================

def authenticate_ws_token(token: Optional[str], db: Session) -> Optional[User]:
    """
    Xác thực token JWT được gửi kèm qua WebSocket query param `?token=...`.
    - Trả về User nếu token hợp lệ và tài khoản đang hoạt động.
    - Trả về None nếu thiếu token, sai chữ ký, hết hạn hoặc tài khoản bị khóa.
    - Covers: BR-5, AC-11
    """
    if not token or not token.strip():
        return None
    try:
        payload = jwt.decode(token.strip(), SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            return None
        stmt = select(User).where(User.id == user_id, User.isActive.is_(True))
        user = db.scalars(stmt).first()
        return user
    except Exception:
        return None


def verify_conversation_member(conversation_id: int, user_id: int, db: Session) -> bool:
    """
    Kiểm tra xem user_id có quyền tham gia cuộc hội thoại conversation_id hay không.
    - Bắt buộc user_id phải là buyer_id hoặc seller_id trong bảng Participation.
    - Covers: BR-5, AC-11
    """
    stmt = select(Participation).where(
        Participation.conversation_id == conversation_id,
        or_(
            Participation.buyer_id == user_id,
            Participation.seller_id == user_id
        )
    )
    part = db.scalars(stmt).first()
    return part is not None


def save_websocket_message(
    conversation_id: int,
    sender_id: int,
    content: str,
    attachments: Optional[List[str]],
    db: Session
) -> MessageResponseItem:
    """
    Lưu tin nhắn gửi qua WebSocket vào cơ sở dữ liệu.
    - Cập nhật conversations.last_message_at.
    - Tạo các bản ghi MessageAttachment nếu có ảnh đính kèm.
    - Trả về DTO MessageResponseItem để đóng gói sự kiện broadcast.
    - Covers: AC-12
    """
    now_time = datetime.now(timezone.utc)
    new_msg = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content.strip(),
        is_read=False,
        sent_at=now_time
    )
    db.add(new_msg)
    db.flush()

    att_dtos: List[MessageAttachmentResponse] = []
    if attachments:
        for url in attachments:
            clean_url = str(url).strip()
            if clean_url:
                new_att = MessageAttachment(
                    message_id=new_msg.message_id,
                    file_url=clean_url,
                    file_type="image"
                )
                db.add(new_att)
                db.flush()
                att_dtos.append(
                    MessageAttachmentResponse(
                        attachment_id=new_att.attachment_id,
                        file_url=new_att.file_url,
                        file_type=new_att.file_type
                    )
                )

    conv = db.get(Conversation, conversation_id)
    if conv:
        conv.last_message_at = now_time

    db.commit()
    db.refresh(new_msg)

    return MessageResponseItem(
        message_id=new_msg.message_id,
        conversation_id=new_msg.conversation_id,
        sender_id=new_msg.sender_id,
        content=new_msg.content,
        is_read=new_msg.is_read,
        sent_at=new_msg.sent_at,
        attachments=att_dtos
    )


def mark_websocket_messages_as_read(
    conversation_id: int,
    reader_id: int,
    db: Session
) -> int:
    """
    Đánh dấu tất cả tin nhắn do đối phương gửi trong hội thoại là đã đọc (is_read = True).
    Trả về số lượng tin nhắn đã được cập nhật.
    - Covers: BR-6, AC-12
    """
    stmt_update = (
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_id != reader_id,
            Message.is_read == False
        )
        .values(is_read=True)
    )
    result = db.execute(stmt_update)
    db.commit()
    return result.rowcount or 0


# ==============================================================================
# 6. SELLER REVIEWS & REPUTATION SERVICES (TASK T6: AC-13, AC-14, BR-7, BR-8)
# ==============================================================================

def recalculate_seller_rating(seller_id: int, db: Session) -> float:
    stmt = select(func.avg(ReviewProductConversation.rating)).where(
        ReviewProductConversation.reviewee_id == seller_id
    )
    raw_avg = db.scalar(stmt)
    rating_avg = round(float(raw_avg), 1) if raw_avg is not None else 0.0

    stats = db.get(userStats, seller_id)
    if stats:
        stats.rating_avg = rating_avg
    else:
        stats = userStats(
            user_id=seller_id,
            rating_avg=rating_avg,
            response_rate=0.0
        )
        db.add(stats)

    return rating_avg


def create_review_product(
    user_id: int,
    product_id: int,
    form: ReviewCreate,
    db: Session
) -> ReviewResponse:
    # 1. Kiểm tra sản phẩm tồn tại và chưa bị xóa mềm
    stmt_prod = select(Product).options(selectinload(Product.status)).where(
        Product.product_id == product_id,
        Product.deleted_at.is_(None)
    )
    product = db.scalars(stmt_prod).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm ID {product_id} không tồn tại hoặc đã bị xóa."
        )

    # 2. Kiểm tra điều kiện tin đăng phải ở trạng thái "Đã bán" (Sold)
    is_sold = (product.status_id == 3) or (
        product.status is not None and product.status.status_name.lower() == "sold"
    )
    if not is_sold:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ có thể gửi đánh giá cho người bán sau khi tin đăng đã chuyển sang trạng thái 'Đã bán' (Sold)."
        )

    # 3. Chặn người bán tự đánh giá chính mình
    if product.seller_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự gửi đánh giá cho tin đăng của chính mình."
        )

    # 4. Xác minh vai trò người mua (Quyết định kỹ thuật Q2 & Quy tắc BR-7)
    # Người gửi đánh giá phải là buyer_id được gán trên sản phẩm
    # HOẶC là người đã từng có cuộc hội thoại trao đổi (Conversation) với người bán về sản phẩm này
    is_assigned_buyer = (product.buyer_id == user_id)
    has_chat_history = False

    if not is_assigned_buyer:
        stmt_conv = (
            select(Participation)
            .join(Conversation, Conversation.conversation_id == Participation.conversation_id)
            .where(
                Conversation.product_id == product_id,
                Participation.buyer_id == user_id,
                Participation.seller_id == product.seller_id
            )
        )
        has_chat_history = db.scalars(stmt_conv).first() is not None

    if not is_assigned_buyer and not has_chat_history:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền đánh giá sản phẩm này. Chỉ người mua thực tế hoặc người đã có cuộc hội thoại trao đổi về sản phẩm mới được gửi đánh giá."
        )

    # 5. Kiểm tra chống đánh giá trùng lặp (AC-14)
    # Khóa chính phức hợp: (product_id, reviewer_id, reviewee_id)
    existing_review = db.get(
        ReviewProductConversation,
        (product_id, user_id, product.seller_id)
    )
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã gửi đánh giá cho người bán về sản phẩm này trước đó rồi. Mỗi sản phẩm chỉ được đánh giá một lần."
        )

    # 6. Kiểm tra giới hạn số sao hợp lệ (1 - 5)
    if form.rating < 1 or form.rating > 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Điểm đánh giá bắt buộc phải là số nguyên nằm trong khoảng từ 1 đến 5 sao."
        )

    # 7. Khởi tạo và lưu bản ghi đánh giá
    clean_content = form.content.strip() if form.content and form.content.strip() else None
    new_review = ReviewProductConversation(
        product_id=product_id,
        reviewer_id=user_id,
        reviewee_id=product.seller_id,
        rating=form.rating,
        content=clean_content
    )
    db.add(new_review)
    db.flush()

    # 8. Tự động tính toán lại điểm uy tín và cập nhật user_stats (BR-8, AC-13)
    recalculate_seller_rating(seller_id=product.seller_id, db=db)

    # 9. Commit toàn bộ transaction để đảm bảo tính nhất quán dữ liệu (ACID)
    db.commit()
    db.refresh(new_review)

    # 10. Đóng gói DTO phản hồi
    reviewer_user = db.scalars(
        select(User).options(selectinload(User.profile)).where(User.id == user_id)
    ).first()

    reviewer_dto = UserSummaryResponse(
        user_id=user_id,
        full_name=get_user_display_name(reviewer_user),
        avatar_url=get_user_avatar(reviewer_user)
    )

    created_time = getattr(
        new_review,
        'CreatedAt',
        getattr(new_review, 'created_at', datetime.now(timezone.utc))
    )

    return ReviewResponse(
        product_id=new_review.product_id,
        reviewer=reviewer_dto,
        reviewee_id=new_review.reviewee_id,
        rating=new_review.rating,
        content=new_review.content,
        created_at=created_time
    )


def get_product_reviews(product_id: int, db: Session) -> List[ReviewResponse]:
    """
    Lấy danh sách tất cả các đánh giá của một sản phẩm (Public).
    - Sắp xếp đánh giá mới nhất lên đầu.
    - Nạp thông tin người đánh giá và ảnh đại diện.
    """
    # Kiểm tra sản phẩm tồn tại và chưa bị xóa mềm
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sản phẩm ID {product_id} không tồn tại hoặc đã bị xóa."
        )

    stmt = (
        select(ReviewProductConversation)
        .options(
            selectinload(ReviewProductConversation.reviewer).selectinload(User.profile)
        )
        .where(ReviewProductConversation.product_id == product_id)
        .order_by(
            getattr(ReviewProductConversation, 'CreatedAt', ReviewProductConversation.product_id).desc()
        )
    )
    reviews = db.scalars(stmt).all()

    result: List[ReviewResponse] = []
    for rev in reviews:
        reviewer_dto = UserSummaryResponse(
            user_id=rev.reviewer_id,
            full_name=get_user_display_name(rev.reviewer),
            avatar_url=get_user_avatar(rev.reviewer)
        )
        created_time = getattr(
            rev,
            'CreatedAt',
            getattr(rev, 'created_at', datetime.now(timezone.utc))
        )
        result.append(
            ReviewResponse(
                product_id=rev.product_id,
                reviewer=reviewer_dto,
                reviewee_id=rev.reviewee_id,
                rating=rev.rating,
                content=rev.content,
                created_at=created_time
            )
        )
    return result


def get_seller_reviews(
    seller_id: int,
    page: int = 1,
    page_size: int = 10,
    db: Session = None
) -> SellerReviewsResponse:
    """
    Xem điểm uy tín và danh sách nhận xét đánh giá của người bán kèm phân trang (Public).
    - Trả về điểm trung bình rating_avg (từ user_stats hoặc tự tính).
    - Trả về tổng số lượt đánh giá total_reviews.
    - Danh sách đánh giá nhận được sắp xếp mới nhất trước.
    """
    # 1. Kiểm tra người dùng tồn tại
    seller = db.get(User, seller_id)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Người dùng ID {seller_id} không tồn tại trong hệ thống."
        )

    # 2. Lấy điểm uy tín từ user_stats
    stats = db.get(userStats, seller_id)
    if stats and stats.rating_avg is not None:
        rating_avg = stats.rating_avg
    else:
        avg_stmt = select(func.avg(ReviewProductConversation.rating)).where(
            ReviewProductConversation.reviewee_id == seller_id
        )
        raw_avg = db.scalar(avg_stmt)
        rating_avg = round(float(raw_avg), 1) if raw_avg is not None else 0.0

    # 3. Đếm tổng số lượt đánh giá nhận được
    count_stmt = select(func.count()).select_from(ReviewProductConversation).where(
        ReviewProductConversation.reviewee_id == seller_id
    )
    total_reviews = db.scalar(count_stmt) or 0

    # 4. Phân trang danh sách đánh giá
    offset = (page - 1) * page_size
    stmt = (
        select(ReviewProductConversation)
        .options(
            selectinload(ReviewProductConversation.reviewer).selectinload(User.profile)
        )
        .where(ReviewProductConversation.reviewee_id == seller_id)
        .order_by(
            getattr(ReviewProductConversation, 'CreatedAt', ReviewProductConversation.product_id).desc()
        )
        .offset(offset)
        .limit(page_size)
    )
    reviews = db.scalars(stmt).all()

    # 5. Đóng gói danh sách reviews
    items: List[ReviewResponse] = []
    for rev in reviews:
        reviewer_dto = UserSummaryResponse(
            user_id=rev.reviewer_id,
            full_name=get_user_display_name(rev.reviewer),
            avatar_url=get_user_avatar(rev.reviewer)
        )
        created_time = getattr(
            rev,
            'CreatedAt',
            getattr(rev, 'created_at', datetime.now(timezone.utc))
        )
        items.append(
            ReviewResponse(
                product_id=rev.product_id,
                reviewer=reviewer_dto,
                reviewee_id=rev.reviewee_id,
                rating=rev.rating,
                content=rev.content,
                created_at=created_time
            )
        )

    return SellerReviewsResponse(
        seller_id=seller_id,
        rating_avg=rating_avg,
        total_reviews=total_reviews,
        page=page,
        page_size=page_size,
        reviews=items
    )


# ==============================================================================
# POTENTIAL BUYERS, FOLLOW & REAL-TIME NOTIFICATION SERVICES (SEQ 7, 8, 11)
# ==============================================================================

def get_potential_buyers_for_product(product_id: int, seller_id: int, db: Session) -> List[PotentialBuyerResponse]:
    """
    Lấy danh sách những người mua tiềm năng đã từng chat về sản phẩm (Seq 7 - Bước 1).
    Chỉ Người bán (chủ tin đăng) mới có quyền gọi API này.
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sản phẩm")
    if product.seller_id != seller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không phải là chủ sở hữu của tin đăng này")

    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.participation).selectinload(Participation.buyer).selectinload(User.profile)
        )
        .where(Conversation.product_id == product_id)
        .order_by(Conversation.last_message_at.desc())
    )
    conversations = db.scalars(stmt).all()

    buyers_map: Dict[int, PotentialBuyerResponse] = {}
    for conv in conversations:
        for part in conv.participation:
            buyer_user = part.buyer
            if buyer_user and buyer_user.id != seller_id and buyer_user.id not in buyers_map:
                buyers_map[buyer_user.id] = PotentialBuyerResponse(
                    user_id=buyer_user.id,
                    full_name=get_user_display_name(buyer_user),
                    avatar_url=get_user_avatar(buyer_user),
                    conversation_id=conv.conversation_id,
                    last_message_at=conv.last_message_at
                )

    return list(buyers_map.values())


async def toggle_follow_user(follower_id: int, followed_id: int, db: Session) -> FollowToggleResponse:
    """
    Thực hiện Theo dõi hoặc Hủy theo dõi một người dùng (Seq 11).
    Tự động tạo Notification và Push Real-time cho người được follow khi bắt đầu theo dõi.
    """
    if follower_id == followed_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự theo dõi chính tài khoản của mình."
        )

    target_user = db.get(User, followed_id)
    if not target_user or not target_user.isActive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng bạn muốn theo dõi không tồn tại hoặc đã bị khóa."
        )

    follower_user = db.get(User, follower_id)

    stmt = select(Follow).where(Follow.follower_id == follower_id, Follow.followed_id == followed_id)
    existing_follow = db.scalars(stmt).first()

    if existing_follow:
        db.delete(existing_follow)
        db.commit()
        is_following = False
        msg = f"Đã hủy theo dõi {get_user_display_name(target_user)}"
    else:
        new_follow = Follow(follower_id=follower_id, followed_id=followed_id)
        db.add(new_follow)

        # Tạo Notification ("User A vừa theo dõi bạn") gửi cho User B (Seq 11)
        follower_name = get_user_display_name(follower_user)
        follow_noti = Notification(
            user_id=followed_id,
            title="Có người theo dõi mới",
            message=f"{follower_name} vừa bắt đầu theo dõi bạn.",
            action_link=f"/user/{follower_id}",
            is_read=False
        )
        db.add(follow_noti)
        db.commit()
        db.refresh(follow_noti)

        is_following = True
        msg = f"Đã bắt đầu theo dõi {get_user_display_name(target_user)}"

        # (Bất đồng bộ) Push thông báo Real-time cho User B
        try:
            await manager.send_to_user(followed_id, {
                "type": "new_notification",
                "data": {
                    "notification_id": follow_noti.notification_id,
                    "title": follow_noti.title,
                    "message": follow_noti.message,
                    "action_link": follow_noti.action_link,
                    "is_read": False,
                    "tag": "new_follower"
                }
            })
        except Exception:
            pass

    stmt_count = select(func.count()).select_from(Follow).where(Follow.followed_id == followed_id)
    total_followers = db.scalar(stmt_count) or 0

    return FollowToggleResponse(
        followed_id=followed_id,
        is_following=is_following,
        message=msg,
        total_followers=total_followers
    )


def check_follow_status(current_user_id: Optional[int], target_user_id: int, db: Session) -> FollowStatusResponse:
    """Kiểm tra xem current_user có đang theo dõi target_user không kèm số lượng follower/following"""
    target_user = db.get(User, target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Người dùng không tồn tại")

    is_following = False
    if current_user_id and current_user_id != target_user_id:
        stmt = select(Follow).where(Follow.follower_id == current_user_id, Follow.followed_id == target_user_id)
        is_following = db.scalars(stmt).first() is not None

    stmt_followers = select(func.count()).select_from(Follow).where(Follow.followed_id == target_user_id)
    stmt_following = select(func.count()).select_from(Follow).where(Follow.follower_id == target_user_id)

    total_followers = db.scalar(stmt_followers) or 0
    total_following = db.scalar(stmt_following) or 0

    return FollowStatusResponse(
        user_id=target_user_id,
        is_following=is_following,
        total_followers=total_followers,
        total_following=total_following
    )


async def process_mark_sold_and_notify_buyer(
    product_id: int,
    seller_id: int,
    buyer_id: Optional[int],
    db: Session
):
    """
    Xử lý toàn vẹn BƯỚC 1 và kích hoạt BƯỚC 2 của Seq 7:
    1. Cập nhật Product: status_id = 3 (Sold), gán buyer_id.
    2. Nếu có chọn Buyer: Tạo bản ghi Notification mời đánh giá.
    3. Đẩy thông báo Real-time (Push Notification) tới Buyer nếu đang Online.
    """
    product = db.get(Product, product_id)
    if not product or product.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy sản phẩm")
    if product.seller_id != seller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền thay đổi trạng thái tin này")

    product.status_id = 3  # Sold
    created_notification = None

    if buyer_id:
        if buyer_id == seller_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Người bán không thể tự chọn mình làm người mua")
        
        buyer_user = db.get(User, buyer_id)
        if not buyer_user or not buyer_user.isActive:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người mua được chọn không tồn tại hoặc đã bị khóa")

        product.buyer_id = buyer_id

        created_notification = Notification(
            user_id=buyer_id,
            title="Mời bạn đánh giá giao dịch",
            message=f"Bạn vừa hoàn tất mua món đồ '{product.title}'. Hãy để lại đánh giá 1-5 sao cho người bán nhé!",
            action_link=f"/product/{product_id}?open_review=true",
            is_read=False
        )
        db.add(created_notification)

    db.commit()
    db.refresh(product)
    if created_notification:
        db.refresh(created_notification)

        noti_payload = {
            "type": "new_notification",
            "data": {
                "notification_id": created_notification.notification_id,
                "title": created_notification.title,
                "message": created_notification.message,
                "action_link": created_notification.action_link,
                "is_read": False,
                "tag": "review_invitation",
                "product_id": product_id,
                "seller_id": seller_id
            }
        }
        await manager.send_to_user(buyer_id, noti_payload)

    return {
        "message": "Đã cập nhật trạng thái tin thành 'ĐÃ BÁN' và gửi lời mời đánh giá cho người mua.",
        "product_id": product_id,
        "status": "Sold",
        "buyer_id": buyer_id,
        "notification_sent": created_notification is not None
    }


def get_user_notifications(user_id: int, db: Session, limit: int = 20) -> List[Notification]:
    """Lấy danh sách thông báo của người dùng (Seq 7 Bước 2, Seq 8)."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.notification_id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_unread_notifications_count(user_id: int, db: Session) -> dict:
    """Đếm số lượng thông báo chưa đọc phục vụ render Badge count chấm đỏ (Seq 8)."""
    stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id,
        Notification.is_read == False
    )
    count = db.scalar(stmt) or 0
    return {"user_id": user_id, "unread_count": count}


def mark_notification_as_read(notification_id: int, user_id: int, db: Session):
    """Đánh dấu thông báo là đã đọc khi người dùng click (Seq 7 Bước 2, Seq 8)."""
    noti = db.get(Notification, notification_id)
    if not noti or noti.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thông báo")
    noti.is_read = True
    db.commit()
    return {"message": "Đã đánh dấu thông báo là đã đọc"}


def mark_all_notifications_as_read(user_id: int, db: Session):
    """Đánh dấu toàn bộ thông báo của người dùng là đã đọc (Seq 8)."""
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    db.execute(stmt)
    db.commit()
    return {"message": "Đã đánh dấu tất cả thông báo là đã đọc"}


# ==============================================================================
# REPORT SERVICES (SEQ 5, SRS USE CASE 2.4)
# ==============================================================================

def get_all_report_reasons(db: Session):
    """
    Lấy danh sách tất cả lý do báo cáo chuẩn hóa từ CSDL (Public).
    """
    stmt = select(ReportReason).order_by(ReportReason.reason_id.asc())
    return db.scalars(stmt).all()


def create_user_report(
    reporter_id: int,
    form: ReportCreate,
    db: Session
) -> ReportResponse:
    """
    Xử lý gửi báo cáo vi phạm từ người dùng với đầy đủ kiểm tra nghiệp vụ và chống spam.
    """
    # 1. Kiểm tra lý do báo cáo có tồn tại trong hệ thống không
    reason = db.get(ReportReason, form.reason_id)
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lý do báo cáo ID {form.reason_id} không tồn tại trong danh mục."
        )

    # 2. Kiểm tra sự tồn tại của đối tượng bị báo cáo & Chặn tự tố cáo chính mình
    if form.target_type == "Product":
        product = db.get(Product, form.target_id)
        if not product or product.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm bị tố cáo không tồn tại hoặc đã bị xóa.")
        if product.seller_id == reporter_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bạn không thể tự gửi báo cáo vi phạm tin đăng của chính mình.")

    elif form.target_type == "User":
        if form.target_id == reporter_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bạn không thể tự gửi báo cáo tài khoản của chính mình.")
        target_user = db.get(User, form.target_id)
        if not target_user or not target_user.isActive:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng bị tố cáo không tồn tại hoặc đã bị khóa.")

    elif form.target_type == "Comment":
        comment = db.get(Comment, form.target_id)
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bình luận bị tố cáo không tồn tại.")
        if comment.user_id == reporter_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bạn không thể tự gửi báo cáo bình luận của chính mình.")

    # 3. Kiểm tra chống Spam (Nếu đã có báo cáo Pending cho cùng đối tượng)
    stmt_check = select(Report).where(
        Report.reporter_id == reporter_id,
        Report.target_type == form.target_type,
        Report.target_id == form.target_id,
        Report.status == "Pending"
    )
    existing_pending = db.scalars(stmt_check).first()
    if existing_pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã gửi một báo cáo cho đối tượng này và đang chờ Ban quản trị duyệt. Vui lòng không gửi trùng lặp."
        )

    # 4. Tạo bản ghi Report mới
    new_report = Report(
        reporter_id=reporter_id,
        reason_id=form.reason_id,
        target_type=form.target_type,
        target_id=form.target_id,
        status="Pending"
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    created_time = getattr(
        new_report,
        'CreatedAt',
        getattr(new_report, 'created_at', datetime.now(timezone.utc))
    )

    return ReportResponse(
        report_id=new_report.report_id,
        reporter_id=new_report.reporter_id,
        target_type=new_report.target_type,
        target_id=new_report.target_id,
        reason=ReportReasonResponse.model_validate(reason),
        status=new_report.status,
        created_at=created_time,
        message="Cảm ơn bạn đã gửi báo cáo. Ban quản trị sẽ kiểm duyệt nội dung trong vòng 24h để giữ môi trường chợ sinh viên an toàn!"
    )


def get_my_submitted_reports(user_id: int, db: Session) -> List[UserReportHistoryItem]:
    """Xem lại lịch sử các báo cáo do chính người dùng gửi và trạng thái xử lý"""
    stmt = (
        select(Report)
        .options(selectinload(Report.reason))
        .where(Report.reporter_id == user_id)
        .order_by(Report.report_id.desc())
    )
    reports = db.scalars(stmt).all()

    items: List[UserReportHistoryItem] = []
    for rep in reports:
        created_time = getattr(rep, 'CreatedAt', getattr(rep, 'created_at', datetime.now(timezone.utc)))
        items.append(
            UserReportHistoryItem(
                report_id=rep.report_id,
                target_type=rep.target_type,
                target_id=rep.target_id,
                reason_content=rep.reason.content if rep.reason else "Khác",
                status=rep.status,
                created_at=created_time
            )
        )
    return items


# ==============================================================================
# FOLLOWERS & FOLLOWING SERVICES (SEQ 11)
# ==============================================================================

def get_user_followers_list(
    target_user_id: int,
    current_user_id: Optional[int],
    page: int = 1,
    page_size: int = 20,
    db: Session = None
) -> PaginatedFollowersResponse:
    """
    Lấy danh sách chi tiết những người đang theo dõi target_user_id (Followers).
    """
    target = db.get(User, target_user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại.")

    stmt_base = (
        select(Follow)
        .options(selectinload(Follow.follower).selectinload(User.profile))
        .where(Follow.followed_id == target_user_id)
        .order_by(Follow.created_at.desc())
    )

    stmt_count = select(func.count()).select_from(Follow).where(Follow.followed_id == target_user_id)
    total = db.scalar(stmt_count) or 0

    offset = (page - 1) * page_size
    follows = db.scalars(stmt_base.offset(offset).limit(page_size)).all()

    following_ids_set = set()
    if current_user_id:
        stmt_my_following = select(Follow.followed_id).where(Follow.follower_id == current_user_id)
        following_ids_set = set(db.scalars(stmt_my_following).all())

    items: List[FollowUserItemResponse] = []
    for f in follows:
        user_obj = f.follower
        items.append(
            FollowUserItemResponse(
                user_id=user_obj.id,
                full_name=get_user_display_name(user_obj),
                avatar_url=get_user_avatar(user_obj),
                bio=user_obj.profile.bio if user_obj.profile else None,
                followed_at=f.created_at or datetime.now(timezone.utc),
                is_following_back=(user_obj.id in following_ids_set)
            )
        )

    return PaginatedFollowersResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )


def get_user_following_list(
    target_user_id: int,
    current_user_id: Optional[int],
    page: int = 1,
    page_size: int = 20,
    db: Session = None
) -> PaginatedFollowersResponse:
    """
    Lấy danh sách chi tiết những người mà target_user_id đang theo dõi (Following).
    """
    target = db.get(User, target_user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại.")

    stmt_base = (
        select(Follow)
        .options(selectinload(Follow.followed).selectinload(User.profile))
        .where(Follow.follower_id == target_user_id)
        .order_by(Follow.created_at.desc())
    )

    stmt_count = select(func.count()).select_from(Follow).where(Follow.follower_id == target_user_id)
    total = db.scalar(stmt_count) or 0

    offset = (page - 1) * page_size
    follows = db.scalars(stmt_base.offset(offset).limit(page_size)).all()

    following_ids_set = set()
    if current_user_id:
        stmt_my_following = select(Follow.followed_id).where(Follow.follower_id == current_user_id)
        following_ids_set = set(db.scalars(stmt_my_following).all())

    items: List[FollowUserItemResponse] = []
    for f in follows:
        user_obj = f.followed
        items.append(
            FollowUserItemResponse(
                user_id=user_obj.id,
                full_name=get_user_display_name(user_obj),
                avatar_url=get_user_avatar(user_obj),
                bio=user_obj.profile.bio if user_obj.profile else None,
                followed_at=f.created_at or datetime.now(timezone.utc),
                is_following_back=(user_obj.id in following_ids_set)
            )
        )

    return PaginatedFollowersResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items
    )

