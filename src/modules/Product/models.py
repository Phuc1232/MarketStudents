from src.Core.database import Base
from sqlalchemy import Column, String,Boolean,INTEGER,text, ForeignKey, Text, Float, DateTime, func
from sqlalchemy.sql.expression import null
from sqlalchemy.orm import relationship
from src.Core.models import Timestamp

class Category(Base):
    __tablename__ = 'categories'
    category_id = Column(INTEGER, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True)
    icon_url = Column(Text)

    subcategory = relationship("SubCategory", back_populates="category")

class SubCategory(Base):
    __tablename__ = 'sub_categories'
    sub_category_id = Column(INTEGER, primary_key=True, index=True)
    category_id = Column(INTEGER, ForeignKey('categories.category_id'))
    name = Column(String(100), nullable=False)

    category = relationship("Category", back_populates="subcategory")
    products= relationship("Product", back_populates="subcategory")
    attribute=relationship("Attribute", back_populates="subcategory")
class Product(Base, Timestamp):
    __tablename__ = 'products'
    product_id = Column(INTEGER, primary_key=True, index=True)
    seller_id = Column(INTEGER, ForeignKey('user.id'))
    sub_category_id = Column(INTEGER, ForeignKey('sub_categories.sub_category_id'))
    status_id = Column(INTEGER, ForeignKey('product_statuses.status_id'))
    condition_id = Column(INTEGER, ForeignKey('product_condition.condition_id'))
    buyer_id = Column(INTEGER, ForeignKey('user.id'), nullable=True)
    
    title = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    description = Column(Text)
    thumbnails = Column(Text)
    deleted_at = Column(DateTime(timezone=True), nullable=True) # Soft delete
    
    # Relationships
    subcategory = relationship("SubCategory", back_populates="products")
    status = relationship("ProductStatus", back_populates="products")
    condition = relationship("ProductCondition", back_populates="products")
    images = relationship("ProductImage", back_populates="product")
    views = relationship("ProductView", back_populates="product")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="products_sold")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="products_bought")
    reviews = relationship("ReviewProductConversation", back_populates="product")
    favorited_by = relationship("Favorite", back_populates="product")
    value=relationship("ProductAttribute", back_populates="product")
    address=relationship("Address", back_populates='product')
    comment=relationship("Comment", back_populates="product")
class ProductImage(Base):
    __tablename__ = 'product_images'
    image_id = Column(INTEGER, primary_key=True, index=True)
    product_id = Column(INTEGER, ForeignKey('products.product_id'))
    image_url = Column(Text, nullable=False)
    display_order = Column(INTEGER, default=0)
    is_thumbnail = Column(Boolean, default=False)

    product = relationship("Product", back_populates="images")
    

class ProductCondition(Base):
    __tablename__="product_condition"
    condition_id=Column(INTEGER, primary_key=True)
    condition_name=Column(String, nullable=False)
    desc=Column(String, nullable=True)

    products = relationship("Product", back_populates="condition")

class ProductStatus(Base):
    __tablename__ = 'product_statuses'
    status_id = Column(INTEGER, primary_key=True, index=True)
    status_name = Column(String(50), nullable=False)
    color_code = Column(String(10))

    products = relationship("Product", back_populates="status")

class ProductView(Base):
    __tablename__ = 'product_views'
    view_id = Column(INTEGER, primary_key=True, index=True)
    product_id = Column(INTEGER, ForeignKey('products.product_id'))
    user_id=Column(INTEGER, ForeignKey('user.id'))
    viewed_at = Column(DateTime(timezone=True), server_default=func.now())

    user=relationship('User', back_populates='views')
    product = relationship("Product", back_populates="views")
# --- MÔ HÌNH THUỘC TÍNH ĐỘNG (EAV PATTERN) ---
class Attribute(Base):
    __tablename__ = 'attributes'
    attribute_id = Column(INTEGER, primary_key=True, index=True)
    name = Column(String(100)) # Ví dụ: RAM, Màu sắc
    data_type = Column(String(50))
    subcategory_id=Column(INTEGER, ForeignKey('sub_categories.sub_category_id'), nullable=False)

    subcategory=relationship('SubCategory', back_populates='attribute')
    value=relationship("ProductAttribute", back_populates="attribute")
    option=relationship("AttributeOption", back_populates="attribute")
class AttributeOption(Base):
    __tablename__ = 'attribute_options'
    option_id = Column(INTEGER, primary_key=True, index=True)
    attribute_id = Column(INTEGER, ForeignKey('attributes.attribute_id'))
    option_value = Column(String(100)) # Ví dụ: 8GB, Đỏ

    attribute=relationship("Attribute", back_populates="option")

class ProductAttribute(Base):
    # Bảng trung gian nối Sản phẩm - Thuộc tính 
    __tablename__ = 'product_attributes'
    id = Column(INTEGER, primary_key=True, index=True)
    product_id = Column(INTEGER, ForeignKey('products.product_id'))
    attribute_id = Column(INTEGER, ForeignKey('attributes.attribute_id'))
    Value_Text=Column(String, nullable=True)
    Value_Num=Column(String, nullable=False)

    product = relationship("Product", back_populates="value")
    attribute=relationship("Attribute", back_populates="value")

