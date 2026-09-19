from src.Core.database import Base
from sqlalchemy.sql import func
from sqlalchemy import Column, String,Boolean,INTEGER,ForeignKey,Text,text,Float,DateTime,JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import null
from src.Core.models import Timestamp

class User(Base, Timestamp):
    __tablename__="user"
    id=Column(INTEGER, primary_key=True, nullable=False)
    Email=Column(String, nullable=False, unique=True)
    PassWord=Column(String, nullable=True)
    isActive=Column(Boolean, server_default=text("true"))
    account_type=Column(String(15), default="Ca Nhan", nullable=True)
    role_id=Column(INTEGER, ForeignKey("roles.role_id"), server_default=text("2"))

    profile=relationship("userProfile", back_populates="user", uselist=False)
    stats=relationship("userStats", back_populates="user", uselist=False)
    verification=relationship("StudentVerification", back_populates="user", uselist=False)
    
    address=relationship("Address", back_populates="user")
    wallet=relationship("Wallet", back_populates="user")
    role=relationship("Role", back_populates="user")
    login_histories = relationship("LoginHistory", back_populates="user")
    blacklists = relationship("Blacklist", back_populates="user")
    saved_searches = relationship("SavedSearch", back_populates="user")
    following = relationship("Follow", foreign_keys="[Follow.follower_id]", back_populates="follower")
    followers = relationship("Follow", foreign_keys="[Follow.followed_id]", back_populates="followed")
    products_sold = relationship("Product", foreign_keys="[Product.seller_id]", back_populates="seller")
    products_bought = relationship("Product", foreign_keys="[Product.buyer_id]", back_populates="buyer")
    reviews_given = relationship("ReviewProductConversation", foreign_keys="[ReviewProductConversation.reviewer_id]", back_populates="reviewer")
    reviews_received = relationship("ReviewProductConversation", foreign_keys="[ReviewProductConversation.reviewee_id]", back_populates="reviewee")
    favorites = relationship("Favorite", back_populates="user")
    report=relationship("Report", back_populates="user")
    comment=relationship("Comment", back_populates="user")
    # commentreply=relationship('CommentReply', back_populates='user')
    notification=relationship('Notification', back_populates='user')
    systemlog=relationship('SystemLog', back_populates='admin') 
    usersub=relationship('UserSubscription', back_populates='user')
    views=relationship("ProductView", back_populates='user')
    seller_participation=relationship("Participation", foreign_keys="[Participation.seller_id]", back_populates='seller')
    buyer_participation=relationship("Participation",foreign_keys="[Participation.buyer_id]", back_populates="buyer")
    message=relationship("Message", back_populates='sender')
    transaction=relationship("PaymentTransaction", back_populates='user')
    violator=relationship("IdentityVerification", foreign_keys="[IdentityVerification.user_id]", back_populates="user")
    handler=relationship("IdentityVerification", foreign_keys="[IdentityVerification.handle_by_id]", back_populates='handle')
    provider=relationship("User_Providers", back_populates="user")
class User_Providers(Base, Timestamp):
    __tablename__="user_providers"
    id=Column(INTEGER, primary_key=True, index=True)
    user_id=Column(INTEGER, ForeignKey("user.id"), nullable=False)
    provider_name=Column(String, nullable=False)
    provider_id=Column(String, nullable=True)
    access_toke=Column(Text, nullable=True)
    refesh_token=Column(Text, nullable=True)

    user=relationship("User", back_populates="provider")
class userProfile(Base):
    __tablename__ = 'user_profiles'
    user_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone_number = Column(String(20))
    avatar_url = Column(Text)
    bio = Column(Text)
    type_mode = Column(String(20), default="light") # Giao diện sáng/tối
    user = relationship("User", back_populates="profile")

class userStats(Base):
    __tablename__ = 'user_stats'
    user_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True)
    rating_avg = Column(Float, default=0.0)
    response_rate = Column(Float, default=0.0)
    joined_date = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="stats")

class StudentVerification(Base):
    __tablename__ = 'student_verifications'
    user_id = Column(INTEGER, ForeignKey('user.id'), primary_key=True)
    edu_email = Column(String(255))
    student_card_img = Column(Text)
    status = Column(String(50), default="Pending")
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="verification")

class Address(Base):
    __tablename__ = 'addresses'
    address_id = Column(INTEGER, primary_key=True, index=True)
    user_id = Column(INTEGER, ForeignKey('user.id'))
    product_id=Column(INTEGER, ForeignKey('products.product_id'))
    ward_id = Column(INTEGER, ForeignKey('master_wards.ward_id')) # Nối với bản đồ
    specific_name = Column(String(255), nullable=False) # Số nhà, tên đường
    type = Column(String(50), nullable=False) # Nhà riêng, Công ty
    is_default = Column(Boolean, server_default=text("True"))

    user = relationship("User", back_populates="address")
    product=relationship("Product", back_populates="address")
    ward = relationship("MasterWard", back_populates="address")
class LoginHistory(Base, Timestamp):
    __tablename__ = 'login_histories'
    history_id = Column(INTEGER, primary_key=True, index=True)
    user_id = Column(INTEGER, ForeignKey('user.id'))
    ip_address = Column(String(50))
    device_info = Column(Text)
    login_time = Column(DateTime(timezone=True), server_default=func.now())
    user=relationship("User", back_populates="login_histories")

class Blacklist(Base):
    __tablename__ = 'blacklists'
    blacklist_id = Column(INTEGER, primary_key=True, index=True)
    admin_id = Column(INTEGER, ForeignKey('user.id')) # Người thực hiện chặn
    blocked_value = Column(String(255)) # Email/SĐT bị chặn
    reason = Column(Text)

    user = relationship("User", back_populates="blacklists")
class IdentityVerification(Base):
    __tablename__="identity_verification"
    request_id=Column(INTEGER, primary_key=True, index=True)
    user_id=Column(INTEGER, ForeignKey("user.id"), nullable=False)
    handle_by_id=Column(INTEGER, ForeignKey("user.id"), nullable=False)
    contact_phone=Column(String, nullable=False)
    other_phone=Column(String, nullable=True)
    cccd_front_url=Column(Text, nullable=False)
    cccd_back_url=Column(Text, nullable=False)
    sim_ownership_url=Column(Text, nullable=False)
    note=Column(String, nullable=True)
    submit_at=Column(DateTime(timezone=True), server_default=func.now())

    user=relationship("User", foreign_keys=[user_id], back_populates='violator')
    handle=relationship("User", foreign_keys=[handle_by_id], back_populates="handler")
class SavedSearch(Base):
    __tablename__ = 'saved_searches'
    search_id = Column(INTEGER, primary_key=True, index=True)
    user_id = Column(INTEGER, ForeignKey('user.id'))
    keyword = Column(String(255))
    filter_criteria = Column(JSON) # Lưu chuỗi JSON cực kỳ tiện lợi

    user = relationship("User", back_populates="saved_searches")