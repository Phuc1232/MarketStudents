from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, and_, or_, update
from fastapi import HTTPException, status
from typing import Optional, List, Dict
from datetime import datetime, timezone
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
    MessageCreate, PaginatedMessagesResponse, ProductSummaryResponse, MessageResponse
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

def create_product_comment(
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
