# 电商运营智能客服

基于 LangGraph + RAG 的电商智能客服系统，支持意图识别、多轮对话、订单查询、投诉分析和知识库管理。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Uvicorn |
| Agent 编排 | LangGraph（状态图驱动） |
| 大模型 | 通义千问（Qwen3-Max / Qwen-Turbo） |
| 向量检索 | ChromaDB + text-embedding-v4 + BM25（RRF 融合） |
| 关系数据库 | PostgreSQL（information_db / chat_db 双 Schema） |
| 缓存 & 记忆 | Redis（历史缓存 + 摘要持久化） |
| 数据库迁移 | Alembic |
| 前端 | React 18 + TypeScript + Vite + TailwindCSS |

## 项目结构

```
电商运营智能客服/
├── backend/
│   ├── main.py              # FastAPI 入口，14 个 API 端点
│   ├── agent.py             # LangGraph Agent（意图→闲聊/咨询/查询/投诉）
│   ├── intent_classifier.py # 意图分类器
│   ├── vector_stores.py     # RAG 服务（ChromaDB + BM25 + RRF）
│   ├── knowledge_base.py    # 知识库向量化与检索
│   ├── memory_manager.py    # 三层渐进遗忘记忆管理
│   ├── file_history_store.py# 对话持久化（PostgreSQL + Redis）
│   ├── order_service.py     # 订单查询服务
│   ├── file_parser.py       # 文件解析（txt/pdf/docx）
│   ├── schema.py / config_data.py
│   ├── auth/                # 认证模块（JWT + bcrypt）
│   ├── chat/                # ChatMessage ORM 模型
│   └── alembic/             # 数据库迁移脚本
├── frontend/
│   └── src/
│       ├── components/      # ChatArea / MessageBubble / KbUploadPage / ChatPage
│       ├── api/             # Axios API 封装
│       ├── types/           # TypeScript 类型定义
│       └── hooks/           # React Hooks
├── requirements.txt
└── start.txt
```

## 功能架构

```
用户输入
  │
  ▼
意图分类（Qwen-Turbo）
  │
  ├─ 闲聊 ──→ 多轮对话（三层记忆 + LLM 生成）
  ├─ 咨询 ──→ RAG 检索（ChromaDB + BM25 RRF 融合）
  │           ├─ 普通咨询 → 向量检索 → LLM 回答
  │           ├─ 商品对比 → 多商品分别检索 → LLM 对比分析
  │           └─ 库存查询 → LLM 提取关键词 → PostgreSQL 查询
  ├─ 查询 ──→ 订单号提取 → PostgreSQL 查询 → 格式化返回
  └─ 投诉 ──→ LLM 情绪分析（高/中/低 + 分类） → 安抚回复 / 转人工
```

## 记忆管理（三层渐进遗忘）

| 层 | 存储 | 容量 | 生命周期 |
|---|---|---|---|
| 活跃窗口 | Python TTLCache | 最近 20 轮原文 | 1 小时 |
| 对话摘要 | Redis | 压缩摘要（≤200 字） | 永久（删除会话时清理） |
| 核心事实 | Redis | 用户偏好/需求要点（≤5 条） | 永久（删除会话时清理） |

超过 10 轮后，最早对话自动压缩进摘要层；用户提起旧话题时，摘要 + 核心事实注入 prompt 兜底。

## API 列表

| 端点 | 方法 | 说明 |
|---|---|---|
| `/register` | POST | 用户注册 |
| `/token` | POST | 登录获取 JWT |
| `/me` | GET | 当前用户信息 |
| `/sessions` | GET | 会话列表 |
| `/sessions/{session_id}` | DELETE | 删除会话（软删除） |
| `/sessions/{session_id}/rename` | PUT | 重命名会话 |
| `/chat` | POST | 发送消息（非流式） |
| `/chat/stream` | POST | 发送消息（SSE 流式） |
| `/history/{session_id}` | GET | 获取会话历史 |
| `/upload` | POST | 上传知识库文件 |
| `/kb/files` | GET | 文件列表（分页） |
| `/kb/files/{file_id}` | GET | 文件详情及 chunk 列表 |
| `/kb/files/{file_id}` | DELETE | 删除文件（软删 + ChromaDB 清理） |
| `/kb/chunks/{chunk_id}` | DELETE | 删除单条 chunk |

## 启动步骤

### 前置依赖

- Python 3.11+
- Node.js 18+
- PostgreSQL（需运行中）
- Redis（需运行中）

### 1. 安装后端依赖

```bash
cd backend
pip install -r ../requirements.txt
```

### 2. 配置环境变量

在 `backend/` 下创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key
```

### 3. 数据库迁移

```bash
cd backend
alembic upgrade head
```

### 4. 启动 Redis

```bash
redis-server
```

### 5. 启动后端

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

API 文档：http://127.0.0.1:8000/docs

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 7. 打开浏览器

- 客服对话：http://localhost:5173
- 知识库管理：http://localhost:5173/kb

## 数据库 Schema

```
information_db          chat_db
├── users               ├── chat_messages
├── order_tb            └── alembic_version
├── product_tb
└── knowledge_tb
```

业务数据（用户、订单、商品、知识库）与对话数据分离在不同 Schema，便于独立备份和权限管理。

## 知识库管理

- **去重**：SHA-256 文件哈希，存在即跳过
- **存储**：PostgreSQL `knowledge_tb` 存文件元数据，ChromaDB 存向量 + chunk
- **管理**：前端双 Tab（文件列表 / 上传），支持分页、chunk 预览、单 chunk 删除
- **软删除**：删除文件时 DB 标记 `deleted` + ChromaDB 清理对应 chunk
