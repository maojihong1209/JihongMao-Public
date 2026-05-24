# 标准库
import os

# 第三方包
from langchain_openai import ChatOpenAI
from crewai.llm import LLM

# ---- 模型配置 ----
OPENAI_API_BASE = "https://api.wlai.vip/v1"
OPENAI_CHAT_API_KEY = "sk-xxx"
OPENAI_CHAT_MODEL = "gpt-4o-mini"

ONEAPI_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
ONEAPI_CHAT_API_KEY = "sk-xxx"
ONEAPI_CHAT_MODEL = "qwen-max"

OLLAMA_API_BASE = "http://192.168.2.9:11434/v1"
OLLAMA_CHAT_API_KEY = ""
OLLAMA_CHAT_MODEL = "llama3.1:latest"

SERPER_API_KEY = "xxx"

MODEL_TYPE = "oneapi"
model = None


def init_model():
    """初始化 LLM 模型，供 Streamlit 调用。"""
    global model
    os.environ["SERPER_API_KEY"] = SERPER_API_KEY
    if MODEL_TYPE == "oneapi":
        model = LLM(
            api_base=ONEAPI_API_BASE,
            api_key=ONEAPI_CHAT_API_KEY,
            model=ONEAPI_CHAT_MODEL,
        )
    elif MODEL_TYPE == "ollama":
        os.environ["OPENAI_API_KEY"] = "NA"
        model = ChatOpenAI(
            base_url=OLLAMA_API_BASE,
            api_key=OLLAMA_CHAT_API_KEY,
            model=OLLAMA_CHAT_MODEL,
            temperature=0.7,
        )
    else:
        model = ChatOpenAI(
            base_url=OPENAI_API_BASE,
            api_key=OPENAI_CHAT_API_KEY,
            model=OPENAI_CHAT_MODEL,
        )
    print("LLM 初始化完成")
