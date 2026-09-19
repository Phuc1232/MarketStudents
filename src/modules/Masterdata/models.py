from src.Core.database import Base
from sqlalchemy import Column, String , INTEGER, ForeignKey
from sqlalchemy.orm import relationship



class MasterProvince(Base):
    __tablename__ = 'master_provinces'
    province_id = Column(INTEGER, primary_key=True, index=True)
    province_name = Column(String(100), nullable=False)
    province_type = Column(String(50))
    code = Column(String(20), unique=True)
    districts = relationship("MasterDistrict", back_populates="province")

class MasterDistrict(Base):
    __tablename__ = 'master_districts'
    district_id = Column(INTEGER, primary_key=True, index=True)
    province_id = Column(INTEGER, ForeignKey('master_provinces.province_id'))
    district_name = Column(String(100), nullable=True)
    district_type = Column(String(50))
    province = relationship("MasterProvince", back_populates="districts")
    wards = relationship("MasterWard", back_populates="district")

class MasterWard(Base):
    __tablename__ = 'master_wards'
    ward_id = Column(INTEGER, primary_key=True, index=True)
    district_id = Column(INTEGER, ForeignKey('master_districts.district_id'))
    ward_name = Column(String(100), nullable=False)
    ward_type = Column(String(50))
    district = relationship("MasterDistrict", back_populates="wards")
    address = relationship("Address", back_populates="ward")

# --- PHÂN QUYỀN & DANH MỤC CƠ BẢN ---
class Role(Base):
    __tablename__ = 'roles'
    role_id = Column(INTEGER, primary_key=True, index=True)
    role_name = Column(String(50), unique=True, nullable=False)

    user=relationship("User", back_populates="role")
