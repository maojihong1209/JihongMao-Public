import json, asyncio
from typing import Sequence, List

import redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, message_to_dict, HumanMessage, AIMessage

import config_data as config

# ---- Redis 连接池 ----
redis_pool = redis.ConnectionPool(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    max_connections=50,
)
sync_redis = redis.Redis(connection_pool=redis_pool, encoding="utf-8", decode_responses=True)


# ---- LangChain 历史存储（RAG chain 内部用，存 Redis） ----
class RedisChatMessageHistory(BaseChatMessageHistory):
    """LangChain 兼容的历史存储（仅供 RAG chain 的 RunnableWithMessageHistory 使用）"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.key = f"rag_history:{session_id}"

    def add_messages(self, messages: Sequence[BaseMessage]) -> None:
        current = self.messages
        current.extend(messages)
        data = json.dumps(
            [message_to_dict(m) for m in current], ensure_ascii=False
        )
        sync_redis.setex(self.key, config.SHORT_TERM_MEMORY_TTL, data)

    @property
    def messages(self) -> List[BaseMessage]:
        data = sync_redis.get(self.key)
        if data:
            return messages_from_dict(json.loads(data))
        return []

    def clear(self) -> None:
        sync_redis.delete(self.key)


def get_history(session_id: str) -> RedisChatMessageHistory:
    return RedisChatMessageHistory(session_id)


# ---- 会话标题（Redis，轻量级元数据） ----
def get_session_title(session_id: str) -> str | None:
    try:
        return sync_redis.get(f"session_title:{session_id}")
    except Exception:
        return None


def set_session_title(session_id: str, title: str) -> None:
    sync_redis.set(f"session_title:{session_id}", title)


# ---- 长期记忆：PostgreSQL chat_db.chat_messages ----

async def save_chat_turn(
    db_factory: async_sessionmaker[AsyncSession],
    user_id: int,
    session_id: str,
    username: str,
    input_text: str,
    ai_response,
) -> None:
    """保存一轮对话到 PostgreSQL（长期记忆）。"""
    from chat import ChatMessage

    content = ai_response.content if hasattr(ai_response, "content") else str(ai_response)
    ai_type = ai_response.type if hasattr(ai_response, "type") else "text"
    complaint_level = getattr(ai_response, "complaint_level", None)
    complaint_type = getattr(ai_response, "complaint_type", None)

    async with db_factory() as db:
        db.add_all([
            ChatMessage(
                session_id=session_id,
                user_id=user_id,
                username=username,
                role="user",
                content=input_text,
                msg_type="text",
            ),
            ChatMessage(
                session_id=session_id,
                user_id=user_id,
                username=username,
                role="agent",
                content=content,
                msg_type=ai_type,
                complaint_level=complaint_level,
                complaint_type=complaint_type,
            ),
        ])
        await db.commit()

    # 会话标题（Redis 轻量缓存）
    try:
        title_key = f"session_title:{session_id}"
        if not sync_redis.exists(title_key):
            title = input_text[:20] + ("..." if len(input_text) > 20 else "")
            sync_redis.set(title_key, title)
    except Exception:
        pass


async def get_chat_history(
    db_factory: async_sessionmaker[AsyncSession],
    session_id: str,
) -> list[dict]:
    """查询某个会话的完整历史（供前端 history API 使用）。"""
    from chat import ChatMessage

    async with db_factory() as db:
        result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.status == "active",
            )
            .order_by(ChatMessage.created_at)
        )
        rows = result.scalars().all()

    messages = []
    for row in rows:
        if row.role == "user":
            messages.append({"role": "user", "content": row.content})
        else:
            msg = {
                "role": "agent",
                "content": row.content,
                "type": row.msg_type,
            }
            if row.complaint_level:
                msg["complaintLevel"] = row.complaint_level
            if row.complaint_type:
                msg["complaintType"] = row.complaint_type
            messages.append(msg)
    return messages


async def get_user_sessions(
    db_factory: async_sessionmaker[AsyncSession],
    user_id: int,
) -> list[dict]:
    """查询某用户的所有会话列表（供前端会话列表使用）。"""
    from chat import ChatMessage

    async with db_factory() as db:
        result = await db.execute(
            select(ChatMessage.session_id)
            .where(
                ChatMessage.user_id == user_id,
                ChatMessage.status == "active",
            )
            .distinct()
            .order_by(ChatMessage.session_id.desc())
        )
        session_ids = [row[0] for row in result.all()]

    sessions = []
    for sid in session_ids:
        title = get_session_title(sid)
        if not title:
            title = "新对话"
        sessions.append({"id": sid, "title": title})

    return sessions


async def delete_session_data(session_id: str, db_factory: async_sessionmaker[AsyncSession] = None) -> None:
    """软删除会话：PostgreSQL 标记 deleted + 清理 Redis 缓存。"""
    if db_factory:
        try:
            from chat import ChatMessage
            async with db_factory() as db:
                await db.execute(
                    update(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .values(status="deleted")
                )
                await db.commit()
        except Exception:
            pass

    # Redis（缓存清理，因为没有状态字段，直接删）
    try:
        sync_redis.delete(
            f"session_title:{session_id}",
            f"rag_history:{session_id}",
            f"memory_summary:{session_id}",
            f"memory_facts:{session_id}",
        )
    except Exception:
        pass


# ---- async wrappers ----
async def save_chat_turn_async(db_factory, user_id, session_id, username, input_text, result) -> None:
    await save_chat_turn(db_factory, user_id, session_id, username, input_text, result.get("ai_response", result))


async def get_chat_history_async(db_factory, session_id: str) -> list[dict]:
    return await get_chat_history(db_factory, session_id)


async def get_user_sessions_async(db_factory, user_id: int) -> list[dict]:
    return await get_user_sessions(db_factory, user_id)


async def get_session_title_async(session_id: str) -> str | None:
    return await asyncio.to_thread(get_session_title, session_id)


async def set_session_title_async(session_id: str, title: str) -> None:
    await asyncio.to_thread(set_session_title, session_id, title)


async def delete_session_data_async(session_id: str, db_factory=None) -> None:
    await delete_session_data(session_id, db_factory)
