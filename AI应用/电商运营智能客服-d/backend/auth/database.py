# auth/database.py
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# 使用 asyncpg 驱动，连接字符串需改为 postgresql+asyncpg://
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL 未设置")
# 将原有 postgresql:// 替换为 postgresql+asyncpg://
async_db_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    async_db_url,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {"search_path": "information_db, chat_db"}
    },
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db