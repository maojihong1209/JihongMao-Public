import os, logging
from langchain_community.chat_models.tongyi import ChatTongyi
from dotenv import load_dotenv
from file_history_store import get_short_memory, get_session_summary
import config_data as config

load_dotenv()
logger = logging.getLogger(__name__)


class MemoryManager:
    """两层记忆管理器。

    Layer 1 — 短期记忆: 近 10 轮对话原文（Redis，多 worker 共享，TTL 24h）
    Layer 2 — 长期记忆: 完整历史（PostgreSQL chat_messages）

    build_context 组装 prompt 时两层拼在一起。
    """

    def __init__(self):
        self.llm = ChatTongyi(
            model=config.chat_model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
        )

    async def build_memory_prefix(self, db_factory, session_id: str) -> str:
        """构建记忆前缀（PG 摘要），用于咨询/查询意图。"""
        summary = await get_session_summary(db_factory, session_id)
        return f"[前期对话摘要]\n{summary}" if summary else ""

    async def build_context(self, db_factory, user_id: int, session_id: str,
                            system_prompt: str, input_text: str) -> str:
        """构建完整 prompt 上下文（Redis 短期记忆 + PG 摘要）。"""
        short_history = get_short_memory(user_id, session_id)
        recent = short_history[-10:] if short_history else []
        recent_str = "\n".join(
            [f"{'用户' if m['role'] == 'user' else '客服'}: {m['content'][:300]}"
             for m in recent]
        ) if recent else "（无近期对话）"

        summary = await get_session_summary(db_factory, session_id)

        parts = [system_prompt]

        if summary:
            parts.append(f"\n\n[前期对话摘要]\n{summary}")

        parts.append(f"\n\n[近期对话]\n{recent_str}")
        parts.append(f"\n\n用户当前问题：{input_text}")

        return "\n".join(parts)

    async def clear_memory(self, user_id: int, session_id: str):
        from file_history_store import delete_short_memory
        try:
            delete_short_memory(user_id, session_id)
        except Exception:
            pass
