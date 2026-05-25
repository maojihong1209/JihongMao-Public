import os, json, logging
from langchain_community.chat_models.tongyi import ChatTongyi
from dotenv import load_dotenv
from file_history_store import sync_redis
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
    """三层渐进遗忘记忆管理器。

    Layer 1 — 活跃窗口: 最近 10 轮对话全文（agent 内存 TTLCache）
    Layer 2 — 对话摘要: 超窗口部分压缩为摘要（存 Redis）
    Layer 3 — 完整历史: 每轮对话原文（存 PostgreSQL）

    遗忘曲线: 最近 6 轮逐字保留 → 摘要逐步压缩 → 旧对话自然淡出
    """

    def __init__(self):
        self.llm = ChatTongyi(
            model=config.chat_model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
        )

    # ---- Redis key 命名 ----
    @staticmethod
    def _summary_key(session_id: str) -> str:
        return f"memory_summary:{session_id}"

    # ---- 读写 Redis ----
    def _get_summary(self, session_id: str) -> str:
        try:
            return sync_redis.get(self._summary_key(session_id)) or ""
        except Exception:
            return ""

    def _set_summary(self, session_id: str, text: str):
        try:
            sync_redis.set(self._summary_key(session_id), text)
        except Exception:
            pass

    # ---- 上下文构建 ----
    def build_memory_prefix(self, session_id: str) -> str:
        """构建记忆前缀（对话摘要），用于已有独立历史管理的意图。"""
        summary = self._get_summary(session_id)
        return f"[前期对话摘要]\n{summary}" if summary else ""

    def build_context(self, session_id: str, system_prompt: str,
                      input_text: str, short_history: list) -> str:
        """构建完整 prompt 上下文，包含三层记忆。"""
        recent = short_history[-10:] if len(short_history) > 0 else []
        recent_str = "\n".join(
            [f"{'用户' if m['role'] == 'user' else '客服'}: {m['content'][:300]}"
             for m in recent]
        ) if recent else "（无近期对话）"

        summary = self._get_summary(session_id)

        parts = [system_prompt]

        if summary:
            parts.append(f"\n\n[前期对话摘要]\n{summary}")

        parts.append(f"\n\n[近期对话]\n{recent_str}")
        parts.append(f"\n\n用户当前问题：{input_text}")

        return "\n".join(parts)

    # ---- 记忆更新（渐进压缩） ----
    def update_memory(self, session_id: str, short_history: list):
        """当活跃窗口超过阈值时，将最早的对话压缩进摘要。"""
        if len(short_history) <= 8:
            return  # 还不够长，无需压缩

        overflow = short_history[:-6]  # 超过6条的部分
        if len(overflow) < 2:
            return

        to_compress = overflow[-4:]  # 取最早的2轮(4条消息)进行压缩
        turns_str = "\n".join(
            [f"{'用户' if m['role'] == 'user' else '客服'}: {m['content'][:200]}"
             for m in to_compress]
        )

        existing = self._get_summary(session_id)

        try:
            prompt = SUMMARY_PROMPT.format(
                existing_summary=existing or "（无）",
                new_turns=turns_str,
            )
            resp = self.llm.invoke(prompt)
            new_summary = resp.content if hasattr(resp, 'content') else str(resp)
            new_summary = new_summary.strip()
            self._set_summary(session_id, new_summary)
            logger.info(f"会话 {session_id} 摘要已更新 ({len(new_summary)} 字)")
        except Exception:
            logger.exception("记忆压缩失败")

    def clear_memory(self, session_id: str):
        """删除会话的记忆缓存。"""
        try:
            sync_redis.delete(self._summary_key(session_id))
        except Exception:
            pass
