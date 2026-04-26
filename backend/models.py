from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    company_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    date = Column(DateTime)
    vendor = Column(String)
    amount = Column(Float)
    risk_score = Column(Integer)
    is_anomaly = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
