import os
from dotenv import load_dotenv
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate
import config_data as config

load_dotenv()

# 优化点1：使用 ChatPromptTemplate，将人设放入 SystemMessage
intent_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是一个精准的电商客服意图分类器。请严格只返回以下四个类别之一：闲聊、咨询、查询、投诉。
分类标准：
- 闲聊：日常问候、无关话题、询问身份等。
- 咨询：商品相关问题，包括：商品推荐、尺码、材质、搭配、库存、有货、缺货、补货、有没有某商品等。
- 查询：订单状态、物流进度、快递单号等（必须有明确订单号或明确指向已下订单）。
- 投诉：表达不满、要求退款、骂人、要求人工等。

请参考以下示例进行判断：
用户：你好，在吗？ -> 闲聊
用户：这件衣服有M码吗？ -> 咨询
用户：牙膏还有货吗？ -> 咨询
用户：有没有库存？ -> 咨询
用户：我的快递到哪了？ -> 查询
用户：你们这是什么破烂质量，我要退钱！ -> 投诉

关键区分：问商品有没有、是否有货、库存多少 -> 咨询；问已下单的物流、订单状态 -> 查询。
要求：不要输出任何标点符号、解释或多余的文字，仅输出类别名称。"""),
    ("human", "{input}")
])


class IntentClassifier(object):
    def __init__(self):
        self.llm = ChatTongyi(
            model=config.intent_model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY")
        )
        self.chain = intent_prompt | self.llm

    def classify(self, text: str) -> str:
        result = self.chain.invoke({"input": text}).content.strip()
        return self.parse_result(result)

    async def aclassify(self, text: str) -> str:
        result = (await self.chain.ainvoke({"input": text})).content.strip()
        return self.parse_result(result)

    def parse_result(self, result: str) -> str:
        valid_intents = {"闲聊", "咨询", "查询", "投诉"}
        if result in valid_intents:
            return result
        for intent in valid_intents:
            if intent in result:
                return intent
        return "闲聊"