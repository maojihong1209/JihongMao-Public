import os, logging
from langchain_community.chat_models.tongyi import ChatTongyi
from dotenv import load_dotenv
from file_history_store import get_short_memory, get_session_summary, set_session_summary
import config_data as config

load_dotenv()
logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """你是一个对话摘要助手。下面是新的对话片段，请将其**合并更新**到已有摘要中。

已有摘要：{existing_summary}

新对话片段：
{new_turns}

请生成更新后的摘要（不超过200字），保留关键信息：用户需求、偏好、重要决策、订单信息等。
只返回摘要文本，不要加前缀。"""


class MemoryManager:
    """两层渐进遗忘记忆管理器。

    Layer 1 — 短期记忆: 近 10 轮对话原文（Redis，多 worker 共享，TTL 24h）
    Layer 2 — 长期记忆: 会话摘要 + 完整历史（PostgreSQL）

    遗忘曲线: 最近 6 轮逐字保留 → 超出部分 LLM 压缩为摘要 → 永久存 PG
    """

    def __init__(self):
        self.llm = ChatTongyi(
            model=config.chat_model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
        )

    # ---- 上下文构建 ----

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

    # ---- 记忆更新（异步，直接跑在 event loop 中）----

    async def update_memory(self, db_factory, user_id: int, session_id: str):
        """当短期记忆超过阈值时，将最早对话压缩进摘要（存 PG）。"""
        short_history = get_short_memory(user_id, session_id)
        if len(short_history) <= 8:
            return

        overflow = short_history[:-6]
        if len(overflow) < 2:
            return

        to_compress = overflow[-4:]
        turns_str = "\n".join(
            [f"{'用户' if m['role'] == 'user' else '客服'}: {m['content'][:200]}"
             for m in to_compress]
        )

        existing = await get_session_summary(db_factory, session_id)

        try:
            prompt = SUMMARY_PROMPT.format(
                existing_summary=existing or "（无）",
                new_turns=turns_str,
            )
            resp = await self.llm.ainvoke(prompt)
            new_summary = resp.content if hasattr(resp, 'content') else str(resp)
            new_summary = new_summary.strip()
            await set_session_summary(db_factory, session_id, new_summary)
            logger.info(f"会话 {session_id} 摘要已更新 ({len(new_summary)} 字)")
        except Exception:
            logger.exception("记忆压缩失败")

    # ---- 清理 ----

    async def clear_memory(self, db_factory, user_id: int, session_id: str):
        """删除会话的所有记忆（PG 摘要清理已由 delete_session_data 处理）。"""
        from file_history_store import delete_short_memory
        try:
            delete_short_memory(user_id, session_id)
        except Exception:
            pass
