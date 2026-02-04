from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    api_token = Column(String)
    tg_id = Column(Integer, nullable=True)

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True)
    admin_email = Column(String)
    action = Column(String)
    target_email = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
