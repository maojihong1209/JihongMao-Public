# Chroma
collection_name = "rag"
persist_directory = "./chroma_db"

# spliter
chunk_size = 1000
chunk_overlap = 100
separators = ["\n\n", "\n", ".", "!", "?", "。", "！", "？", " ", ""]

# 检索返回TOP K
similarity_number = 1

embedding_model_name = "text-embedding-v4"
chat_model_name = "qwen3-max"
intent_model_name = "qwen-turbo"
session_config = {"configurable": {"session_id": "user_001"}}

# Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# 短期记忆 TTL
SHORT_TERM_MEMORY_TTL = 3600

# 转人工链接
MANUAL_SERVICE_URL = "https://www.xxx.com/人工客服"