from sqlalchemy import Column, INTEGER, String, Text, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.Core.database import Base
from src.Core.models import Timestamp

class Conversation(Base):
    __tablename__ = 'conversations'
    conversation_id = Column(INTEGER, primary_key=True, index=True)
    product_id = Column(INTEGER, ForeignKey('products.product_id'))
    last_message_at = Column(DateTime(timezone=True))
    
    product = relationship("Product")
    participation=relationship('Participation', back_populates='conversation')
    messages = relationship("Message", back_populates="conversation")

class Participation(Base):
    __tablename__='Participation'
    buyer_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True, index=True)
    seller_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True, index=True)
    conversation_id=Column(INTEGER, ForeignKey('conversations.conversation_id'), primary_key=True, index=True)

    buyer = relationship("User", foreign_keys=[buyer_id],back_populates='buyer_participation')
    seller = relationship("User", foreign_keys=[seller_id], back_populates='seller_participation')
    conversation=relationship("Conversation", back_populates='participation')

class Message(Base):
    __tablename__ = 'messages'
    message_id = Column(INTEGER, primary_key=True, index=True)
    conversation_id = Column(INTEGER, ForeignKey('conversations.conversation_id'))
    sender_id = Column(INTEGER, ForeignKey('user.id'))
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates='message')
    attachments = relationship("MessageAttachment", back_populates="message")

class MessageAttachment(Base):
    __tablename__ = 'message_attachments'
    attachment_id = Column(INTEGER, primary_key=True, index=True)
    message_id = Column(INTEGER, ForeignKey('messages.message_id'))
    file_url = Column(Text, nullable=False)
    file_type = Column(String(50))
    message = relationship("Message", back_populates="attachments")

class Comment(Base, Timestamp):
    __tablename__ = 'comments'
    comment_id = Column(INTEGER, primary_key=True, index=True)
    product_id = Column(INTEGER, ForeignKey('products.product_id'))
    user_id = Column(INTEGER, ForeignKey('user.id'))
    content = Column(Text, nullable=False)
    parent_id=Column(INTEGER, ForeignKey('comments.comment_id'))

    parent=relationship("Comment", remote_side="Comment.comment_id", back_populates="children")
    children=relationship("Comment", back_populates='parent')
    product = relationship("Product", back_populates="comment")
    user = relationship("User", back_populates="comment")
    

# class CommentReply(Base, Timestamp):
#     __tablename__ = 'comment_replies'
#     reply_id = Column(INTEGER, primary_key=True, index=True)
#     comment_id = Column(INTEGER, ForeignKey('comments.comment_id'))
#     user_id = Column(INTEGER, ForeignKey('user.id'))
#     content = Column(Text, nullable=False)
    
#     comment = relationship("Comment", back_populates="replies")
#     user = relationship("User", back_populates='replies')

class Report(Base, Timestamp):
    __tablename__ = 'reports'
    report_id = Column(INTEGER, primary_key=True, index=True)
    reporter_id = Column(INTEGER, ForeignKey('user.id'))
    reason_id = Column(INTEGER, ForeignKey('report_reason.reason_id'))
    target_type = Column(String(50)) # Product, User, Comment
    target_id = Column(INTEGER) # ID của mục bị report
    status = Column(String(50), default="Pending")
    
    user = relationship("User", back_populates='report')
    reason = relationship("ReportReason", back_populates="report")

class ReportReason(Base):
    __tablename__="report_reason"
    reason_id=Column(INTEGER, primary_key=True, index=True)
    content=Column(String, nullable=False)

    report=relationship("Report", back_populates='reason')

class Notification(Base, Timestamp):
    __tablename__ = 'notifications'
    notification_id = Column(INTEGER, primary_key=True, index=True)
    user_id = Column(INTEGER, ForeignKey('user.id'))
    title = Column(String(255), nullable=False)
    message = Column(Text)
    action_link = Column(Text)
    is_read = Column(Boolean, default=False)
    
    user = relationship("User", back_populates='notification')

class Follow(Base):
    __tablename__ = 'follows'
    
    # Cả 2 cột đều trỏ về bảng users
    follower_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True ) # Người đi follow
    followed_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True) # Người được follow
    
    # Thời gian bắt đầu theo dõi
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Quan hệ logic
    follower = relationship("User", foreign_keys=[follower_id], back_populates="following")
    followed = relationship("User", foreign_keys=[followed_id], back_populates="followers")

class ReviewProductConversation(Base, Timestamp):
    __tablename__ = 'review_product_conversations'
    
    # 3 cột này kết hợp lại thành 1 Khóa chính (Composite Primary Key)
    product_id = Column(INTEGER, ForeignKey('products.product_id'), primary_key=True)
    reviewer_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True) # Người đánh giá (Buyer)
    reviewee_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True) # Người bị đánh giá (Seller)
    
    rating = Column(INTEGER, nullable=False) # VD: 1 đến 5
    content = Column(Text)
    
    # Quan hệ logic
    product = relationship("Product", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviews_given")
    reviewee = relationship("User", foreign_keys=[reviewee_id], back_populates="reviews_received")

class Favorite(Base):
    __tablename__ = 'favorites'
    
    # Khóa chính kết hợp (Composite Primary Key) từ 2 khóa ngoại
    user_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True)
    product_id = Column(INTEGER, ForeignKey('products.product_id'), primary_key=True)
    
    # Thời gian bấm thả tim
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Quan hệ logic 2 chiều
    user = relationship("User", back_populates="favorites")
    product = relationship("Product", back_populates="favorited_by")
class SystemLog(Base):
    __tablename__ = 'system_logs'
    log_id = Column(INTEGER, primary_key=True, index=True)
    admin_id = Column(INTEGER, ForeignKey('user.id'))
    action = Column(String(100))
    target_table = Column(String(100))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    admin = relationship("User", back_populates="systemlog")