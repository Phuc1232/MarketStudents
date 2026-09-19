from src.Core.database import Base
from sqlalchemy import Column, INTEGER, String, Float, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from src.Core.models import Timestamp

class Wallet(Base):
    __tablename__ = 'wallets'
    wallet_id = Column(INTEGER, primary_key=True, index=True)
    user_id = Column(INTEGER, ForeignKey('user.id'), unique=True)
    currency = Column(Float, default=0.0) # Số tiền hiện tại

    user = relationship("User", back_populates="wallet")
    histories = relationship("WalletHistory", back_populates="wallet")

class WalletHistory(Base, Timestamp):
    __tablename__ = 'wallet_histories'
    history_id = Column(INTEGER, primary_key=True, index=True)
    wallet_id = Column(INTEGER, ForeignKey('wallets.wallet_id'))
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50)) # Nạp tiền, Trừ phí
    status = Column(String(50))
    description = Column(Text)
    payment_id=Column(INTEGER, ForeignKey("payment_transactions.payment_id"), nullable=True)
    subscription_id = Column(INTEGER, ForeignKey('user_subscriptions.subscription_id'), nullable=True)

    payment = relationship("PaymentTransaction", back_populates="histories")
    subscription = relationship("UserSubscription", back_populates="histories")
    wallet = relationship("Wallet", back_populates="histories")

class PaymentTransaction(Base, Timestamp):
    __tablename__ = 'payment_transactions'
    payment_id = Column(INTEGER, primary_key=True, index=True)
    user_id = Column(INTEGER, ForeignKey('user.id'))
    amount = Column(Float, nullable=False)
    gateway = Column(String(50))
    gateway_transaction_id = Column(String(255))
    status = Column(String(50))
    raw_response = Column(Text)
    
    user = relationship("User", back_populates="transaction")
    histories=relationship("WalletHistory", back_populates="payment")


class ServicePackage(Base):
    __tablename__ = 'service_packages'
    package_id = Column(INTEGER, primary_key=True, index=True)
    package_name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    duration = Column(INTEGER)
    student_discount = Column(Float, default=0.0)
    
    subscriptions = relationship("UserSubscription", back_populates="package")

class UserSubscription(Base, Timestamp):
    __tablename__ = 'user_subscriptions'
    subscription_id = Column(INTEGER, primary_key=True, index=True)
    user_id = Column(INTEGER, ForeignKey('user.id'))
    package_id = Column(INTEGER, ForeignKey('service_packages.package_id'))
    status = Column(String(50))
    is_auto_renew = Column(Boolean, default=False)
    
    user = relationship("User", back_populates='usersub')
    package = relationship("ServicePackage", back_populates="subscriptions")
    histories=relationship("WalletHistory", back_populates="subscription")



