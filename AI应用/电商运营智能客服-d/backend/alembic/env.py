import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth.database import Base
from auth import models      # noqa: F401 — User/Order/Product
import chat                  # noqa: F401 — ChatMessage

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 从 .env 读取数据库 URL，适配异步驱动
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
db_url = os.getenv("DATABASE_URL", "")
config.set_main_option(
    "sqlalchemy.url",
    db_url.replace("postgresql://", "postgresql+asyncpg://"),
)


async def run_async_migrations():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from sqlalchemy import text

    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        # 确保 schema 存在
        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS information_db"))
        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS chat_db"))
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="chat_db",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_async_migrations())
