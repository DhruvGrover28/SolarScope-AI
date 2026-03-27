from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    projects = relationship("Project", back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    method = Column(String, nullable=False)
    image_path = Column(String, nullable=True)
    mask_path = Column(String, nullable=True)
    usable_area_m2 = Column(Float, nullable=False, default=0.0)
    panel_count = Column(Integer, nullable=False, default=0)
    power_kw = Column(Float, nullable=False, default=0.0)
    annual_kwh = Column(Float, nullable=False, default=0.0)
    installation_cost = Column(Float, nullable=False, default=0.0)
    annual_savings = Column(Float, nullable=False, default=0.0)
    payback_years = Column(Float, nullable=False, default=0.0)
    total_savings_25yrs = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    assumptions = Column(JSON, nullable=True)
    source_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="projects")
