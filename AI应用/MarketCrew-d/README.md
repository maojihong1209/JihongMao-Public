# 🚀 MarketCrew

基于 [CrewAI](https://github.com/crewAIInc/crewAI) 构建的 AI 多 Agent 虚拟营销团队。输入项目需求，自动完成从需求分析到营销方案输出的全流程协作。

## 工作流程

```
用户输入 → 项目经理 → 市场分析师 → 营销战略师(3 方案) → 内容创作师(3 创意 + 文案) → 内容审核员 → 最终方案(.docx)
```

5 个 Agent 串联协作，上游输出作为下游输入。市场分析师和营销战略师可按需进行网络搜索（ReAct 模式）。

## 团队角色

| Agent | 角色 | 职责 |
|---|---|---|
| 🧑‍💼 项目经理 | Project Manager | 拆解需求，制定任务简报，为下游提供执行指引 |
| 📊 市场分析师 | Market Analyst | 市场调研、竞品分析、受众洞察，可联网搜索 |
| 📈 营销战略师 | Marketing Strategist | 制定 3 个差异化备选战略（稳健/创新/平衡），含战术、渠道、KPI |
| ✏️ 内容创作师 | Content Creator | 策划 3 个活动创意 + 撰写对应营销文案 |
| 🔍 内容审核员 | Content Reviewer | 审核品牌风险、敏感词、事实错误、战略匹配度，修正后输出最终版 |

## 环境要求

- Python >= 3.10
- [Serper API Key](https://serper.dev)（Agent 联网搜索需要）

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 编辑 main.py 配置模型和 API Key
#    MODEL_TYPE = "oneapi"   # oneapi / openai / ollama
#    ONEAPI_CHAT_API_KEY = "sk-..."
#    SERPER_API_KEY = "..."

# 3. 启动
streamlit run app.py
```

浏览器访问 `http://localhost:8501`，输入项目名称和描述，点击"开始分析"。

## 模型配置

编辑 `main.py`，支持三种模型类型：

```python
MODEL_TYPE = "oneapi"   # oneapi: 通义千问等国产大模型
                        # openai : GPT 系列
                        # ollama : 本地大模型（需安装 Ollama）

# 以 oneapi（通义千问）为例：
ONEAPI_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
ONEAPI_CHAT_API_KEY = "sk-..."       # 替换为你的 API Key
ONEAPI_CHAT_MODEL = "qwen-max"

# 搜索引擎 API Key（必填）
SERPER_API_KEY = "..."              # 申请: https://serper.dev
```

## 输出文件

| 目录 | 说明 |
|---|---|
| `chat_history/` | 对话历史（JSON），文件命名：`{日期}_{项目名称}.json` |
| `market_program/` | 最终方案文档（.docx），旧版自动备份到 `.archive/` |

## 项目结构

```
MarketCrew/
├── app.py              # Streamlit 前端主程序
├── main.py             # 模型配置与初始化
├── shared_state.py     # 跨线程通信（Queue）
├── crew.py             # Agent / Task / Crew 定义
├── models.py           # Pydantic 数据模型
├── requirements.txt    # 项目依赖
├── config/
│   ├── agents.yaml     # Agent 角色与目标定义
│   └── tasks.yaml      # Task 指令与期望输出
├── storage/
│   ├── store.py        # 对话历史存取
│   └── docx_gen.py     # 方案文档生成
├── chat_history/       # 对话历史（自动生成）
└── market_program/     # 方案文档（自动生成）
```

## 技术栈

- [CrewAI](https://crewai.com) — 多 Agent 协作框架
- [Streamlit](https://streamlit.io) — Web 前端
- [Pydantic](https://docs.pydantic.dev) — 结构化输出
- [python-docx](https://python-docx.readthedocs.io) — 文档生成
- [LangChain](https://www.langchain.com) — LLM 适配层
