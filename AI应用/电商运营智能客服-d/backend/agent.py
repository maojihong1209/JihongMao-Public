import os, re, asyncio, json, logging
from langchain_community.chat_models.tongyi import ChatTongyi
from dotenv import load_dotenv
import config_data as config
from intent_classifier import IntentClassifier
from order_service import OrderService
from schema import AIResponse
from vector_stores import RagService
from memory_manager import MemoryManager
from file_history_store import get_short_memory, set_short_memory

logger = logging.getLogger(__name__)
load_dotenv()


def check_compliance_text(text: str) -> bool:
    forbidden = ["暴力", "血腥", "色情", "政治敏感"]
    for word in forbidden:
        if word in text:
            return False
    return True


CHITCHAT_SYSTEM_PROMPT = """你是鸿途服装的官方客服"小鸿"，性格亲切、专业、耐心。

你的职责：
- 热情问候客户，介绍自己
- 回答关于服装尺码、材质、搭配、洗涤保养等问题
- 引导客户说出具体需求（身高体重、喜好风格、预算等）
- 如需查订单，引导客户提供订单号
- 如遇投诉，安抚情绪并记录反馈

注意：不要编造品牌故事，不要承诺不确定的优惠，始终以帮助客户解决问题为目标。"""

COMPLAINT_ANALYSIS_PROMPT = """你是一个电商客服投诉分析助手。请分析以下用户投诉，**严格只返回一行JSON**（不要markdown代码块，不要解释）：

{"level":"低/中/高","type":"物流/质量/服务态度/其他","reply":"你的回复内容"}

分类标准：
- level 低：一般不满，可以正常沟通解决
- level 中：明显不满，需要认真安抚并给出解决方案
- level 高：极度愤怒，威胁差评、曝光、12315投诉等，必须优先转人工处理
- type 物流：快递慢、丢件、少件、包裹破损
- type 质量：商品瑕疵、缩水、褪色、与描述不符
- type 服务态度：客服态度差、回复慢、敷衍
- type 其他：不属于以上分类的投诉

用户投诉：{input_text}"""

COMPARISON_KEYWORDS = ["对比", "比较", "vs", "哪个好", "区别", "哪个更", "选哪个", "有什么不同", "差别", "优缺点"]

INVENTORY_KEYWORDS = ["库存", "有货", "现货", "缺货", "补货", "断货", "卖光", "卖完", "还有吗", "还有没有", "有没有货", "有多少", "多少件", "多少库存", "还能买", "能买到", "下架"]
INVENTORY_STOP_WORDS = {"库存", "有货", "现货", "缺货", "补货", "断货", "卖光", "卖完", "还有吗", "还有没有", "有没有货", "有多少", "多少件", "多少库存", "还能买", "能买到", "下架", "吗", "呢", "啊", "吧", "了", "的", "这件", "那个", "这个", "你们", "有", "没有", "多少", "还能", "可以"}

TAG_ANALYSIS_PROMPT = """根据对话内容，判断用户特征，从以下标签中选择适用的（可多选，逗号分隔）：
价格敏感、品质控、成分党、急脾气、老客户、比价型、冲动消费、犹豫型、售后倾向

仅返回标签名称，不要解释，不要换行。

对话：
{conversation}"""


class CustomerServiceAgent:
    """鸿途客服 Agent —— 流式为主，非流式为辅。"""

    def __init__(self, intent_classifier, rag_service, db_factory):
        self.intent_classifier = intent_classifier
        self.rag_service = rag_service
        self.db_factory = db_factory
        self.chat_llm = ChatTongyi(
            model=config.chat_model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
        )
        self.memory = MemoryManager()

        self.handlers = {
            "闲聊": self.handle_chitchat,
            "咨询": self.handle_consult,
            "查询": self.handle_query,
            "投诉": self.handle_complaint,
        }

    # ============================================================
    # 统一入口
    # ============================================================

    async def invoke(self, user_id, username, session_id, input_text):
        """非流式调用，返回 ChatOutput。"""
        from schema import ChatOutput

        short_history = get_short_memory(user_id, session_id)

        intent = await self.intent_classifier.aclassify(input_text)
        handler = self.handlers.get(intent, self.handle_unknown)
        result = await handler(user_id, username, session_id, input_text, short_history)

        full_content = result["full_content"]
        ai_type = result.get("ai_type", "text")
        complaint_level = result.get("complaint_level")
        complaint_type = result.get("complaint_type")

        short_history.append({"role": "user", "content": input_text})
        short_history.append({"role": "agent", "content": full_content})
        set_short_memory(user_id, session_id, short_history)

        from file_history_store import save_chat_turn_async
        ai_resp = AIResponse(type=ai_type, content=full_content,
                             complaint_level=complaint_level, complaint_type=complaint_type)
        await save_chat_turn_async(self.db_factory, user_id, session_id, username, input_text, {"ai_response": ai_resp})

        outcome = ChatOutput(
            session_id=session_id, user_id=str(user_id),
            intent=intent, input_text=input_text,
            ai_response=ai_resp,
        )

        asyncio.create_task(self.update_user_tags(user_id, short_history))

        return outcome

    async def stream(self, user_id, username, session_id, input_text):
        """SSE 流式，逐 token 输出。"""
        short_history = get_short_memory(user_id, session_id)

        if not check_compliance_text(input_text):
            blocked = "抱歉，您的消息包含不当内容，请文明交流。"
            yield {"type": "intent", "intent": "违规"}
            yield {"type": "token", "content": blocked}
            yield {"type": "done", "intent": "违规", "ai_response": {"type": "text", "content": blocked}}
            return

        intent = await self.intent_classifier.aclassify(input_text)
        yield {"type": "intent", "intent": intent}

        handler = self.handlers.get(intent, self.handle_unknown)
        result = await handler(user_id, username, session_id, input_text, short_history)
        for event in result.get("events", []):
            yield event

        full_content = result["full_content"]
        ai_type = result.get("ai_type", "text")
        complaint_level = result.get("complaint_level")
        complaint_type = result.get("complaint_type")

        # 更新短期记忆（Redis）
        short_history.append({"role": "user", "content": input_text})
        short_history.append({"role": "agent", "content": full_content})
        set_short_memory(user_id, session_id, short_history)

        # 持久化到 PostgreSQL
        from file_history_store import save_chat_turn_async
        ai_resp = AIResponse(type=ai_type, content=full_content,
                             complaint_level=complaint_level, complaint_type=complaint_type)
        await save_chat_turn_async(self.db_factory, user_id, session_id, username, input_text, {"ai_response": ai_resp})

        done_data = {"type": ai_type, "content": full_content}
        if complaint_level:
            done_data["complaint_level"] = complaint_level
        if complaint_type:
            done_data["complaint_type"] = complaint_type
        yield {"type": "done", "intent": intent, "ai_response": done_data}

        # 异步任务
        asyncio.create_task(self.update_user_tags(user_id, short_history))

    # ============================================================
    # Handler（按意图分发）
    # ============================================================

    async def handle_chitchat(self, user_id, username, session_id, input_text, short_history):
        events = []
        prompt = await self.memory.build_context(self.db_factory, user_id, session_id, CHITCHAT_SYSTEM_PROMPT, input_text)
        prompt += "\n小鸿："
        full_content = ""
        async for chunk in self.chat_llm.astream(prompt):
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if token:
                full_content += token
                events.append({"type": "token", "content": token})
        return {"events": events, "full_content": full_content, "ai_type": "text"}

    async def handle_consult(self, user_id, username, session_id, input_text, short_history):
        events = []
        is_comparison = any(kw in input_text for kw in COMPARISON_KEYWORDS)
        is_inventory = any(kw in input_text for kw in INVENTORY_KEYWORDS)

        if is_comparison:
            full_content = await self.do_comparison(input_text)
            for ch in full_content:
                events.append({"type": "token", "content": ch})
            return {"events": events, "full_content": full_content, "ai_type": "comparison_card"}

        if is_inventory:
            full_content = await self.check_product_stock(input_text)
            for ch in full_content:
                events.append({"type": "token", "content": ch})
            return {"events": events, "full_content": full_content, "ai_type": "text"}

        try:
            memory_prefix = await self.memory.build_memory_prefix(self.db_factory, session_id)
            rag_input = f"{memory_prefix}\n\n用户问题：{input_text}" if memory_prefix else input_text
            full_content = await self.rag_service.chain.ainvoke(
                {"input": rag_input},
                {"configurable": {"session_id": session_id}},
            )
        except Exception:
            logger.exception("RAG 咨询处理失败")
            full_content = "抱歉，暂时无法为您推荐，请稍后再试。"
        events.append({"type": "token", "content": full_content})
        return {"events": events, "full_content": full_content, "ai_type": "text"}

    async def handle_query(self, user_id, username, session_id, input_text, short_history):
        events = []
        memory_prefix = await self.memory.build_memory_prefix(self.db_factory, session_id)
        order_text = await self.do_query(user_id, input_text)

        if memory_prefix:
            enhance_prompt = f"""{memory_prefix}

用户刚查询了订单，查询结果为：
{order_text}

请结合上下文自然地回复用户（如用户之前投诉过，要安抚；如之前咨询过商品，可关联推荐）。直接给出回复："""
            resp = await self.chat_llm.ainvoke(enhance_prompt)
            full_content = resp.content if hasattr(resp, 'content') else str(resp)
            for ch in full_content:
                events.append({"type": "token", "content": ch})
        else:
            full_content = order_text
            events.append({"type": "token", "content": full_content})
        return {"events": events, "full_content": full_content, "ai_type": "text"}

    async def handle_complaint(self, user_id, username, session_id, input_text, short_history):
        events = []
        complaint_level = "中"
        complaint_type = "其他"
        try:
            analysis_prompt = COMPLAINT_ANALYSIS_PROMPT.format(input_text=input_text)
            analysis_resp = await self.chat_llm.ainvoke(analysis_prompt)
            analysis_text = analysis_resp.content if hasattr(analysis_resp, 'content') else str(analysis_resp)
            analysis_text = analysis_text.strip()
            if analysis_text.startswith("```"):
                analysis_text = analysis_text.strip("```json").strip("```").strip()
            analysis = json.loads(analysis_text)
            complaint_level = analysis.get("level", "中")
            complaint_type = analysis.get("type", "其他")
            full_content = analysis.get("reply", "很抱歉给您带来不便，我将为您转接人工。")
        except Exception:
            logger.exception("投诉分析失败")
            full_content = "很抱歉给您带来不便，我已记录您的反馈，将尽快为您处理。"
        for ch in full_content:
            events.append({"type": "token", "content": ch})
        return {"events": events, "full_content": full_content, "ai_type": "human_tip",
                "complaint_level": complaint_level, "complaint_type": complaint_type}

    async def handle_unknown(self, user_id, username, session_id, input_text, short_history):
        full_content = "抱歉，我没有理解您的问题，请换种方式描述一下。"
        return {"events": [{"type": "token", "content": full_content}],
                "full_content": full_content, "ai_type": "text"}

    # ============================================================
    # 业务方法
    # ============================================================

    async def do_query(self, user_id: int, input_text: str) -> str:
        async with self.db_factory() as db:
            order_svc = OrderService(db)
            match = re.search(r"([A-Za-z0-9]+)", input_text)
            if match:
                order = await order_svc.get_order_by_id(match.group(1))
                if order and order.user_id == user_id:
                    card = order_svc.format_order_card(order)
                    return (
                        f"订单号：{card['order_id']}\n"
                        f"商品：{card['product_name']}\n"
                        f"数量：{card['quantity']}\n"
                        f"金额：{card['amount']}元\n"
                        f"物流：{card['logistics_status']}\n"
                        f"时间：{card['order_time']}"
                    )
                return "未找到该订单，请核对订单号。"
            orders = await order_svc.get_orders_by_user(user_id)
            if orders:
                lines = "\n".join([f"{o.order_id}: {o.product_name} ({o.logistics_status})" for o in orders[:5]])
                return f"您最近的订单：\n{lines}"
            return "您当前没有订单。"

    async def do_comparison(self, input_text: str) -> str:
        try:
            extract_prompt = f"""从用户问题中提取需要对比的商品/特征关键词，返回JSON数组。
只返回数组，不要其他内容。
示例：["纯棉T恤", "速干运动衫"]

用户问题：{input_text}"""
            resp = await self.chat_llm.ainvoke(extract_prompt)
            text = resp.content if hasattr(resp, 'content') else str(resp)
            text = text.strip().strip("```json").strip("```").strip()
            items = json.loads(text)
            if not isinstance(items, list) or len(items) < 2:
                items = ["商品A", "商品B"]
        except Exception:
            items = ["商品A", "商品B"]

        all_docs = {}
        for item in items[:3]:
            try:
                docs = self.rag_service.vector_service.vector_store.similarity_search(item, k=2)
                all_docs[item] = "\n".join([d.page_content for d in docs]) if docs else "未找到相关资料"
            except Exception:
                all_docs[item] = "检索失败"

        doc_sections = "\n\n".join([f"【{k}】参考资料：\n{v}" for k, v in all_docs.items()])
        compare_prompt = f"""你是服装导购。根据以下参考资料，对比这些商品，从材质、适用场景、优缺点等维度生成清晰易读的对比分析：

{doc_sections}

用户问题：{input_text}

要求：用自然段落形式呈现，每个对比维度用emoji标注，帮助用户做出选择。"""
        resp = await self.chat_llm.ainvoke(compare_prompt)
        return resp.content if hasattr(resp, 'content') else str(resp)

    async def check_product_stock(self, input_text: str) -> str:
        keyword = await self.extract_product_keyword(input_text)
        if len(keyword) < 2:
            return "请问您想查询哪款商品的库存呢？"
        async with self.db_factory() as db:
            order_svc = OrderService(db)
            products = await order_svc.search_products_by_keyword(keyword)
            if not products:
                return f'抱歉，没有找到与"{keyword}"相关的商品。'
            if len(products) == 1:
                p = products[0]
                card = order_svc.format_product_card(p)
                stock_status = "有货" if card["inventory"] > 0 else "暂时缺货"
                return (
                    f"商品：{card['product_name']}\n"
                    f"库存：{card['inventory']}件（{stock_status}）\n"
                    f"分类：{card['category'] or '暂无分类'}"
                )
            lines = []
            for p in products[:5]:
                card = order_svc.format_product_card(p)
                stock_status = "有货" if card["inventory"] > 0 else "缺货"
                lines.append(f"{card['product_name']}：{card['inventory']}件（{stock_status}）")
            return "为您找到以下商品库存：\n" + "\n".join(lines)

    async def extract_product_keyword(self, input_text: str) -> str:
        prompt = f"""从用户问题中提取要查询的商品名称关键词。只返回一个关键词，不要解释。
示例：
"这件纯棉T恤还有货吗" → 纯棉T恤
"牙膏还有库存吗" → 牙膏
"有没有红色连衣裙" → 红色连衣裙
"牙刷还有吗" → 牙刷

用户问题：{input_text}"""
        try:
            resp = await self.chat_llm.ainvoke(prompt)
            keyword = resp.content if hasattr(resp, 'content') else str(resp)
            return keyword.strip()
        except Exception:
            logger.exception("LLM提取商品关键词失败")
            kw = input_text
            for w in INVENTORY_STOP_WORDS:
                kw = kw.replace(w, "")
            return kw.strip()

    async def update_user_tags(self, user_id: int, short_history: list):
        try:
            recent = short_history[-8:]
            conv_text = "\n".join([
                f"{'用户' if m['role'] == 'user' else '客服'}: {m['content'][:200]}"
                for m in recent
            ])
            if not conv_text:
                return
            prompt = TAG_ANALYSIS_PROMPT.format(conversation=conv_text)
            resp = await self.chat_llm.ainvoke(prompt)
            new_tags = resp.content if hasattr(resp, 'content') else str(resp)
            new_tags = new_tags.strip()

            async with self.db_factory() as db:
                from sqlalchemy import select
                from auth.models import User
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                    return
                existing = set(t.strip() for t in (user.tags or "").split(",") if t.strip())
                new_set = set(t.strip() for t in new_tags.split(",") if t.strip())
                merged = existing | new_set
                merged.discard("新用户")
                if not merged:
                    merged = {"新用户"}
                user.tags = ",".join(sorted(merged))
                await db.commit()
                logger.info(f"用户 {user_id} 标签更新: {user.tags}")
        except Exception:
            logger.exception("用户打标失败")
