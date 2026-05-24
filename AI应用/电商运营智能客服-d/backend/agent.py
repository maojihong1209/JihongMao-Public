
import os, re, asyncio, json, logging
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_community.chat_models.tongyi import ChatTongyi
from dotenv import load_dotenv
import config_data as config
from intent_classifier import IntentClassifier
from order_service import OrderService
from schema import AIResponse, ChatOutput
from vector_stores import RagService
from memory_manager import MemoryManager
from cachetools import TTLCache
logger = logging.getLogger(__name__)
load_dotenv()
short_term_cache = TTLCache(maxsize=1000, ttl=config.SHORT_TERM_MEMORY_TTL)
cache_lock = asyncio.Lock()


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


class AgentState(TypedDict):
    user_id: int
    username: str
    session_id: str
    input_text: str
    intent: str
    ai_response: AIResponse
    chat_history: list


class CustomerServiceAgent:
    def __init__(self, intent_classifier, rag_service, db_factory):
        self.intent_classifier = intent_classifier
        self.rag_service = rag_service
        self.db_factory = db_factory
        self.chat_llm = ChatTongyi(
            model=config.chat_model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
        )
        self.memory = MemoryManager()

        workflow = StateGraph(AgentState)
        workflow.add_node("intent_classify", self.node_intent_classify)
        workflow.add_node("handle_chitchat", self.node_chitchat)
        workflow.add_node("handle_consult", self.node_consult)
        workflow.add_node("handle_query", self.node_query)
        workflow.add_node("handle_complaint", self.node_complaint)

        workflow.set_entry_point("intent_classify")
        workflow.add_conditional_edges("intent_classify", lambda state: state["intent"], {
            "闲聊": "handle_chitchat",
            "咨询": "handle_consult",
            "查询": "handle_query",
            "投诉": "handle_complaint",
        })
        for node in ["handle_chitchat", "handle_consult", "handle_query", "handle_complaint"]:
            workflow.add_edge(node, END)

        self.graph = workflow.compile()

    async def run(self, user_id, username, session_id, input_text):
        cache_key = f"short_memory:{user_id}:{session_id}"
        async with cache_lock:
            short_history = list(short_term_cache.get(cache_key, []))

        state = AgentState(
            user_id=user_id,
            username=username,
            session_id=session_id,
            input_text=input_text,
            intent="",
            ai_response=AIResponse(type="text", content=""),
            chat_history=short_history,
        )

        result = await self.graph.ainvoke(state)

        async with cache_lock:
            short_history.append({"role": "user", "content": input_text})
            short_history.append({"role": "agent", "content": result["ai_response"].content})
            short_term_cache[cache_key] = short_history[-20:]

        from file_history_store import save_chat_turn_async
        await save_chat_turn_async(self.db_factory, user_id, session_id, username, input_text, result)

        return ChatOutput(
            session_id=session_id,
            user_id=str(user_id),
            intent=result["intent"],
            input_text=input_text,
            ai_response=result["ai_response"],
        )

    async def run_stream(self, user_id, username, session_id, input_text):
        """流式运行，逐 token 输出 SSE 事件"""
        cache_key = f"short_memory:{user_id}:{session_id}"
        async with cache_lock:
            short_history = list(short_term_cache.get(cache_key, []))

        if not check_compliance_text(input_text):
            blocked = "抱歉，您的消息包含不当内容，请文明交流。"
            yield {"type": "intent", "intent": "违规"}
            yield {"type": "token", "content": blocked}
            yield {"type": "done", "intent": "违规", "ai_response": {"type": "text", "content": blocked}}
            return

        intent = await self.intent_classifier.aclassify(input_text)
        yield {"type": "intent", "intent": intent}

        ai_type = "text"
        full_content = ""
        complaint_level = None
        complaint_type = None

        if intent == "闲聊":
            prompt = self.memory.build_context(
                session_id, CHITCHAT_SYSTEM_PROMPT, input_text, short_history,
            )
            prompt += "\n小鸿："
            async for chunk in self.chat_llm.astream(prompt):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if token:
                    full_content += token
                    yield {"type": "token", "content": token}

        elif intent == "咨询":
            is_comparison = any(kw in input_text for kw in COMPARISON_KEYWORDS)
            is_inventory = any(kw in input_text for kw in INVENTORY_KEYWORDS)
            if is_comparison:
                ai_type = "comparison_card"
                full_content = await self.do_comparison(input_text)
                for ch in full_content:
                    yield {"type": "token", "content": ch}
            elif is_inventory:
                full_content = await self._check_product_stock(input_text)
                for ch in full_content:
                    yield {"type": "token", "content": ch}
            else:
                try:
                    memory_prefix = self.memory.build_memory_prefix(session_id)
                    rag_input = f"{memory_prefix}\n\n用户问题：{input_text}" if memory_prefix else input_text
                    result = await self.rag_service.chain.ainvoke(
                        {"input": rag_input},
                        {"configurable": {"session_id": session_id}},
                    )
                except Exception:
                    logger.exception("RAG 咨询处理失败")
                    result = "抱歉，暂时无法为您推荐，请稍后再试。"
                full_content = result
                yield {"type": "token", "content": result}

        elif intent == "查询":
            memory_prefix = self.memory.build_memory_prefix(session_id)
            order_text = await self.do_query(user_id, input_text)
            if memory_prefix:
                enhance_prompt = f"""{memory_prefix}

用户刚查询了订单，查询结果为：
{order_text}

请结合上下文自然地回复用户（如用户之前投诉过，要安抚；如之前咨询过商品，可关联推荐）。直接给出回复："""
                resp = await self.chat_llm.ainvoke(enhance_prompt)
                full_content = resp.content if hasattr(resp, 'content') else str(resp)
                for ch in full_content:
                    yield {"type": "token", "content": ch}
            else:
                full_content = order_text
                yield {"type": "token", "content": full_content}

        elif intent == "投诉":
            ai_type = "human_tip"
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
                yield {"type": "token", "content": ch}

        else:
            full_content = "抱歉，我没有理解您的问题，请换种方式描述一下。"
            yield {"type": "token", "content": full_content}

        async with cache_lock:
            short_history.append({"role": "user", "content": input_text})
            short_history.append({"role": "agent", "content": full_content})
            short_term_cache[cache_key] = short_history[-20:]

        from file_history_store import save_chat_turn_async
        ai_resp = AIResponse(type=ai_type, content=full_content,
                             complaint_level=complaint_level, complaint_type=complaint_type)
        result = {"ai_response": ai_resp}
        await save_chat_turn_async(self.db_factory, user_id, session_id, username, input_text, result)

        done_data = {"type": ai_type, "content": full_content}
        if complaint_level:
            done_data["complaint_level"] = complaint_level
        if complaint_type:
            done_data["complaint_type"] = complaint_type
        yield {"type": "done", "intent": intent, "ai_response": done_data}

        # 异步用户打标
        asyncio.create_task(self._update_user_tags(user_id, short_history))

        # 渐进记忆压缩
        asyncio.create_task(asyncio.to_thread(
            self.memory.update_memory, session_id, short_history,
        ))

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
        """多商品对比：提取对比项 -> 分别检索 -> LLM 生成对比分析"""
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

    async def _check_product_stock(self, input_text: str) -> str:
        """检测库存相关问题，查询数据库返回库存信息"""
        # 用 LLM 提取商品关键词
        keyword = await self._extract_product_keyword(input_text)
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

    async def _extract_product_keyword(self, input_text: str) -> str:
        """用 LLM 从用户输入中提取商品名称关键词"""
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
            # 降级：用停用词移除
            kw = input_text
            for w in INVENTORY_STOP_WORDS:
                kw = kw.replace(w, "")
            return kw.strip()

    async def _update_user_tags(self, user_id: int, short_history: list):
        """异步分析对话内容，更新用户标签"""
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

    async def node_intent_classify(self, state: AgentState) -> AgentState:
        state["intent"] = await self.intent_classifier.aclassify(state["input_text"])
        return state

    async def node_chitchat(self, state: AgentState) -> AgentState:
        if not check_compliance_text(state["input_text"]):
            state["ai_response"] = AIResponse(type="text", content="抱歉，您的消息包含不当内容，请文明交流。")
            return state

        history = state.get("chat_history", [])
        prompt = self.memory.build_context(
            state["session_id"], CHITCHAT_SYSTEM_PROMPT,
            state["input_text"], history,
        )
        prompt += "\n小鸿："
        resp = await self.chat_llm.ainvoke(prompt)
        content = resp.content if hasattr(resp, 'content') else str(resp)
        state["ai_response"] = AIResponse(type="text", content=content)
        return state

    async def node_consult(self, state: AgentState) -> AgentState:
        if not check_compliance_text(state["input_text"]):
            state["ai_response"] = AIResponse(type="text", content="抱歉，您的消息包含不当内容，请文明交流。")
            return state

        is_comparison = any(kw in state["input_text"] for kw in COMPARISON_KEYWORDS)
        is_inventory = any(kw in state["input_text"] for kw in INVENTORY_KEYWORDS)
        if is_comparison:
            try:
                content = await self.do_comparison(state["input_text"])
                state["ai_response"] = AIResponse(type="comparison_card", content=content)
            except Exception:
                logger.exception("对比分析失败")
                state["ai_response"] = AIResponse(type="text", content="抱歉，暂时无法为您对比，请稍后再试。")
            return state

        if is_inventory:
            state["ai_response"] = AIResponse(type="text", content=await self._check_product_stock(state["input_text"]))
            return state

        try:
            memory_prefix = self.memory.build_memory_prefix(state["session_id"])
            rag_input = f"{memory_prefix}\n\n用户问题：{state['input_text']}" if memory_prefix else state["input_text"]
            result = await self.rag_service.chain.ainvoke(
                {"input": rag_input},
                {"configurable": {"session_id": state["session_id"]}},
            )
        except Exception:
            logger.exception("RAG 咨询处理失败")
            result = "抱歉，暂时无法为您推荐，请稍后再试。"
        state["ai_response"] = AIResponse(type="text", content=result)
        return state

    async def node_query(self, state: AgentState) -> AgentState:
        async with self.db_factory() as db:
            order_svc = OrderService(db)
            match = re.search(r"([A-Za-z0-9]+)", state["input_text"])
            if match:
                order = await order_svc.get_order_by_id(match.group(1))
                if order and order.user_id == state["user_id"]:
                    card = order_svc.format_order_card(order)
                    text = (
                        f"订单号：{card['order_id']}\n"
                        f"商品：{card['product_name']}\n"
                        f"数量：{card['quantity']}\n"
                        f"金额：{card['amount']}元\n"
                        f"物流：{card['logistics_status']}\n"
                        f"时间：{card['order_time']}"
                    )
                    state["ai_response"] = AIResponse(type="order_card", content=text)
                else:
                    state["ai_response"] = AIResponse(type="text", content="未找到该订单，请核对订单号。")
            else:
                orders = await order_svc.get_orders_by_user(state["user_id"])
                if orders:
                    lines = "\n".join([f"{o.order_id}: {o.product_name} ({o.logistics_status})" for o in orders[:5]])
                    state["ai_response"] = AIResponse(type="text", content=f"您最近的订单：\n{lines}")
                else:
                    state["ai_response"] = AIResponse(type="text", content="您当前没有订单。")
        return state

    async def node_complaint(self, state: AgentState) -> AgentState:
        if not check_compliance_text(state["input_text"]):
            state["ai_response"] = AIResponse(type="text", content="抱歉，您的消息包含不当内容，请文明交流。")
            return state

        complaint_level = "中"
        complaint_type = "其他"
        try:
            analysis_prompt = COMPLAINT_ANALYSIS_PROMPT.format(input_text=state["input_text"])
            analysis_resp = await self.chat_llm.ainvoke(analysis_prompt)
            analysis_text = analysis_resp.content if hasattr(analysis_resp, 'content') else str(analysis_resp)
            analysis_text = analysis_text.strip()
            if analysis_text.startswith("```"):
                analysis_text = analysis_text.strip("```json").strip("```").strip()
            analysis = json.loads(analysis_text)
            complaint_level = analysis.get("level", "中")
            complaint_type = analysis.get("type", "其他")
            reply = analysis.get("reply", "很抱歉给您带来不便，我将为您转接人工。")
        except Exception:
            logger.exception("投诉分析失败")
            reply = "很抱歉给您带来不便，我已记录您的反馈，将尽快为您处理。"

        state["ai_response"] = AIResponse(
            type="human_tip", content=reply,
            complaint_level=complaint_level, complaint_type=complaint_type,
        )
        return state
