from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, ForeignKey
from datetime import datetime, timezone
from pydantic import BaseModel
from .database import Base


# ---- Pydantic 请求/响应模型 ----
class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- SQLAlchemy 数据表模型 ----

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "information_db"}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")
    tags = Column(String, default="新用户")
    created_at = Column(DateTime, default=utcnow)

class Order(Base):
    __tablename__ = "order_tb"
    __table_args__ = {"schema": "information_db"}

    order_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_name = Column(String, nullable=False)
    product_id = Column(String, ForeignKey("product_tb.product_id"), nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    order_time = Column(DateTime, default=utcnow)
    amount = Column(DECIMAL(10, 2), nullable=False)
    logistics_status = Column(String, default="待发货")

class Product(Base):
    __tablename__ = "product_tb"
    __table_args__ = {"schema": "information_db"}

    product_id = Column(String, primary_key=True)
    product_name = Column(String, nullable=False)
    supplier = Column(String)
    category = Column(String)
    inventory = Column(Integer, default=0)


class KnowledgeFile(Base):
    __tablename__ = "knowledge_tb"
    __table_args__ = {"schema": "information_db"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True)
    file_size = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    status = Column(String(10), default="active")
    created_at = Column(DateTime, default=utcnow)
    operator = Column(String(100), default="人工客服")