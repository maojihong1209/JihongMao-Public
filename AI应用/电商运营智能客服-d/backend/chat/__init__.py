from auth.database import Base
from sqlalchemy import Column, Integer, String, Text, DateTime, func


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {"schema": "chat_db"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=False)
    role = Column(String(10), nullable=False)       # 'user' | 'agent'
    content = Column(Text, nullable=False)
    msg_type = Column(String(20), default="text")   # text|order_card|human_tip|comparison_card
    complaint_level = Column(String(10), nullable=True)
    complaint_type = Column(String(20), nullable=True)
    status = Column(String(10), default="active")  # active | deleted
    created_at = Column(DateTime, server_default=func.now())
