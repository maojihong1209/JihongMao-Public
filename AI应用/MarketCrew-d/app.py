# 标准库
import os
import sys
import json
import time
import threading
from datetime import datetime
from io import StringIO

# 第三方包
import streamlit as st
from PyPDF2 import PdfReader
from docx import Document
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 本地模块
import main
from crew import MarketCrew
from shared_state import progress_queue, result_queue
from storage.store import (
    save_conversation, load_conversation, list_conversations,
    generate_filename, delete_conversation,
)
from storage.docx_gen import generate_program_docx

TIMEOUT_SECONDS = 1200

st.set_page_config(page_title="MarketCrew", page_icon="🚀", layout="wide")

ACCENT = "#4F46E5"

st.markdown("""
<style>
    .stApp { background: #f8f9fb; }
    .main .block-container { padding-top: 1rem; max-width: 1100px; }

    .card {
        background: #fff; border: 1px solid #e8eaed; border-left: 3px solid #4F46E5;
        border-radius: 8px; padding: 1.3rem 1.6rem; margin: 0.6rem 0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .card-header {
        font-size: 1rem; font-weight: 600; margin-bottom: 0.7rem;
        padding-bottom: 0.6rem; border-bottom: 1px solid #f1f3f4;
    }

    .phase-box {
        padding: 0.5rem 0.75rem; border-radius: 6px; margin: 0.12rem 0;
        font-size: 0.85rem; font-weight: 500;
    }
    .phase-done { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; }
    .phase-active { background: #fefce8; border: 1px solid #fde68a; color: #854d0e; }
    .phase-pending { background: #f8f9fb; border: 1px solid #e8eaed; color: #a0a5ac; }

    section[data-testid="stSidebar"] .stButton > button {
        border-radius: 6px; text-align: left; font-size: 0.85rem; font-weight: 500;
        padding: 0.45rem 0.8rem; border: none; background: transparent; color: #374151;
    }
    section[data-testid="stSidebar"] .stButton > button:hover { background: #f1f3f4; }

    .stButton > button { border-radius: 6px; font-weight: 500; }
    div[data-testid="stFormSubmitButton"] > button {
        font-weight: 600; padding: 0.55rem 2rem; font-size: 1rem; border-radius: 8px;
    }
    .stTextInput input, .stTextArea textarea {
        border-radius: 6px; border: 1.5px solid #c4c8ce;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #4F46E5; box-shadow: 0 0 0 2px rgba(79,70,229,0.15);
    }

    h2 { font-weight: 600; letter-spacing: -0.01em; }
    h3 { font-weight: 600; font-size: 1.1rem; color: #1f2937; }

    .stProgress > div > div > div { background: #2563EB; }
    .stProgress > div > div { background: #f1f3f4; }

    hr { margin: 0.8rem 0; border-color: #f1f3f4; }
</style>
""", unsafe_allow_html=True)

# ---- 常量 ----
AGENT_ICONS = {
    'pm_output': '🧑‍💼', 'research_report': '🚀', 'market_strategy': '📈',
    'campaign_ideas': '💡', 'copy': '✏️', 'review_result': '🔍',
}
AGENT_NAMES = {
    'pm_output': '项目经理', 'research_report': '市场分析师',
    'market_strategy': '营销战略师', 'campaign_ideas': '活动创意',
    'copy': '营销文案', 'review_result': '内容审核员',
}
AGENT_COLORS = {
    'pm_output': '#7c3aed', 'research_report': '#2563eb',
    'market_strategy': '#d97706', 'campaign_ideas': '#059669',
    'copy': '#db2777', 'review_result': '#0891b2',
}
PROGRESS_PHASES = [
    ('pm_output', '项目需求拆解中...'),
    ('research_report', '市场调研分析中...'),
    ('market_strategy', '营销战略制定中...'),
    ('campaign_ideas', '活动创意策划中...'),
    ('copy', '营销文案撰写中...'),
    ('review_result', '内容质量审核中...'),
]

FIELD_LABELS = {
    'requirement_analysis': '需求分析', 'task_breakdown': '任务拆解',
    'key_guidance': '关键指引', 'market_overview': '市场概况',
    'competitor_analysis': '竞品分析', 'audience_insights': '受众洞察',
    'strategy_a_name': '方案A', 'strategy_a_tactics': '战术', 'strategy_a_channels': '渠道', 'strategy_a_kpis': 'KPI',
    'strategy_b_name': '方案B', 'strategy_b_tactics': '战术', 'strategy_b_channels': '渠道', 'strategy_b_kpis': 'KPI',
    'strategy_c_name': '方案C', 'strategy_c_tactics': '战术', 'strategy_c_channels': '渠道', 'strategy_c_kpis': 'KPI',
    'recommendation': '推荐方案',
    'ideas': '活动创意', 'description': '描述', 'audience': '目标受众', 'channel': '渠道',
    'copies': '营销文案', 'campaign_name': '对应活动', 'title': '标题', 'body': '正文',
    'approved': '审核结论', 'issues_found': '发现的问题',
    'revisions_made': '修正对照', 'corrected_ideas': '修正后活动创意', 'corrected_copies': '修正后文案', 'review_notes': '审核备注',
}

# ---- 初始化 session_state ----
_defaults = {
    'conversations': list_conversations(),
    'current_conv': None,
    'agent_outputs': [],
    'execution_phase': 'input',
    'progress': [],
    'error_msg': '',
    'runner_start_time': 0.0,
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ---- 同步 Queue 数据到 session_state ----
def _drain_queues():
    """每次脚本执行时调用，从 Queue 中取数据同步到 session_state。
    在侧边栏之前调用，确保对话列表第一时间更新。"""
    while True:
        try:
            key = progress_queue.get_nowait()
            if key not in st.session_state.progress:
                st.session_state.progress.append(key)
        except:
            break

    try:
        result = result_queue.get_nowait()
        st.session_state.agent_outputs = result.get('agent_outputs', [])
        st.session_state.error_msg = result.get('error_msg', '')
        st.session_state.execution_phase = result['phase']

        # done 时立即保存对话并更新列表，这样侧边栏渲染前就能看到新记录
        if result['phase'] == 'done' and st.session_state.agent_outputs:
            project_name = st.session_state.get('_last_project_name', '未命名项目')
            filename = generate_filename(project_name)
            conv_data = {
                'filename': filename,
                'project_name': project_name,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'user_input': {
                    'project_name': project_name,
                    'project_description': st.session_state.get('_last_project_desc', ''),
                    'uploaded_files_content': st.session_state.get('_last_uploaded', []),
                },
                'agent_outputs': st.session_state.agent_outputs,
            }
            save_conversation(filename, conv_data)
            st.session_state.conversations = list_conversations()
            st.session_state._completed_outputs = st.session_state.agent_outputs
            st.session_state._saved_docx = True
    except:
        pass


# ---- 清空 Queue（新任务开始前） ----
def _clear_queues():
    while True:
        try:
            progress_queue.get_nowait()
        except:
            break
    while True:
        try:
            result_queue.get_nowait()
        except:
            break


# ---- 辅助函数 ----
def parse_uploaded_file(uploaded_file) -> str:
    try:
        if uploaded_file.name.endswith('.txt'):
            return StringIO(uploaded_file.getvalue().decode('utf-8')).read()
        elif uploaded_file.name.endswith('.pdf'):
            reader = PdfReader(uploaded_file)
            return '\n'.join(page.extract_text() or '' for page in reader.pages)
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(uploaded_file)
            return '\n'.join(p.text for p in doc.paragraphs)
        else:
            return f"[不支持的文件格式: {uploaded_file.name}]"
    except Exception as e:
        return f"[文件解析失败: {str(e)}]"


def _classify_output(json_dict: dict) -> str | None:
    if json_dict is None:
        return None
    keys = set(json_dict.keys())
    if 'task_breakdown' in keys and 'key_guidance' in keys:
        return 'pm_output'
    if 'market_overview' in keys:
        return 'research_report'
    if 'strategy_a_name' in keys and 'recommendation' in keys:
        return 'market_strategy'
    if 'copies' in keys:
        return 'copy'
    if 'ideas' in keys:
        return 'campaign_ideas'
    if 'approved' in keys and 'review_notes' in keys:
        return 'review_result'
    return None


def progress_callback(output):
    """后台线程回调 —— 写入 Queue（Queue 自身线程安全，无需加锁）。"""
    try:
        json_dict = output.json_dict if hasattr(output, 'json_dict') else None
        if json_dict is None:
            return
        key = _classify_output(json_dict)
        if key is None:
            print(f"[progress_callback] 未识别的输出字段: {list(json_dict.keys())}")
            return
        progress_queue.put(key)
        print(f"[progress_callback] 任务完成: {key}")
    except Exception as e:
        print(f"[progress_callback] 异常: {e}")


def _run_crew_thread(project_name: str, project_description: str, uploaded_contents: list):
    """后台线程 —— 执行 CrewAI，结果写入 result_queue。"""
    try:
        if uploaded_contents:
            file_text = '\n'.join(uploaded_contents)
            project_description = f"{project_description}\n\n【用户上传的参考文件内容】\n{file_text}"

        inputs = {
            "project_name": project_name,
            "project_description": project_description,
        }

        if main.model is None:
            raise RuntimeError("LLM 模型未初始化")

        kickoff_result = MarketCrew(main.model, progress_callback=progress_callback).crew().kickoff(inputs=inputs)
        agent_outputs = _extract_task_outputs(kickoff_result)

        result_queue.put({
            'phase': 'done',
            'agent_outputs': agent_outputs,
            'error_msg': '',
        })
    except Exception as e:
        print(f"[_run_crew_thread] 执行异常: {e}")
        result_queue.put({
            'phase': 'error',
            'agent_outputs': [],
            'error_msg': str(e),
        })


def _extract_task_outputs(kickoff_result) -> list:
    outputs = []
    try:
        task_outputs = kickoff_result.tasks_output
        if task_outputs:
            for t in task_outputs:
                json_dict = t.json_dict if hasattr(t, 'json_dict') and t.json_dict else None
                raw = t.raw if hasattr(t, 'raw') else str(t)
                key = _classify_output(json_dict)
                outputs.append({
                    'agent_key': key,
                    'output': json_dict if json_dict else raw,
                })
    except Exception as e:
        print(f"提取任务输出时出错: {e}")
        outputs.append({'agent_key': 'raw_result', 'output': str(kickoff_result)})
    return _apply_review_corrections(outputs)


def _apply_review_corrections(outputs: list) -> list:
    """用审核员的修正版本替换原始活动创意和文案。"""
    review = next((o for o in outputs if o['agent_key'] == 'review_result'), None)
    if not review or not isinstance(review.get('output'), dict):
        return outputs

    review_output = review['output']
    corrected_ideas = review_output.get('corrected_ideas')
    corrected_copies = review_output.get('corrected_copies')

    for o in outputs:
        if o['agent_key'] == 'campaign_ideas' and corrected_ideas:
            o['output'] = {'ideas': corrected_ideas}
        elif o['agent_key'] == 'copy' and corrected_copies:
            o['output'] = {'copies': corrected_copies}

    return outputs


def start_execution(project_name: str, project_description: str, uploaded_contents: list):
    _clear_queues()
    st.session_state.execution_phase = 'running'
    st.session_state.progress = []
    st.session_state.agent_outputs = []
    st.session_state.error_msg = ''
    st.session_state.runner_start_time = time.time()
    thread = threading.Thread(
        target=_run_crew_thread,
        args=(project_name, project_description, uploaded_contents),
        daemon=True,
    )
    thread.start()
    st.session_state.runner_thread = thread


def render_agent_output(output_item: dict):
    agent_key = output_item.get('agent_key', 'unknown')
    output = output_item.get('output', {})
    icon = AGENT_ICONS.get(agent_key, '🤖')
    name = AGENT_NAMES.get(agent_key, agent_key)
    color = AGENT_COLORS.get(agent_key, ACCENT)

    with st.container(border=True):
        st.markdown(f"**{icon}  {name}**")
        if isinstance(output, dict):
            _render_dict(output)
        elif isinstance(output, str):
            st.text(output)
        else:
            st.json(output)


def _render_dict(d: dict):
    """渲染 dict，对 MarketStrategy 的拍平字段自动分组。"""
    # 检测拍平的 strategy 字段并分组渲染
    if 'strategy_a_name' in d:
        st.markdown("**备选方案**")
        for group_key in ('a', 'b', 'c'):
            name = d.get(f'strategy_{group_key}_name', '')
            tactics = d.get(f'strategy_{group_key}_tactics', [])
            channels = d.get(f'strategy_{group_key}_channels', [])
            kpis = d.get(f'strategy_{group_key}_kpis', [])
            st.markdown(f"&ensp;▸ **{name}**")
            if tactics:
                st.markdown(f"&ensp;&ensp;&ensp;*战术*")
                for t in tactics:
                    st.markdown(f"&ensp;&ensp;&ensp;&ensp;• {t}")
            if channels:
                st.markdown(f"&ensp;&ensp;&ensp;*渠道*")
                for c in channels:
                    st.markdown(f"&ensp;&ensp;&ensp;&ensp;• {c}")
            if kpis:
                st.markdown(f"&ensp;&ensp;&ensp;*KPI*")
                for k in kpis:
                    st.markdown(f"&ensp;&ensp;&ensp;&ensp;• {k}")
        # 推荐方案
        rec = d.get('recommendation', '')
        if rec:
            st.markdown(f"**推荐方案**")
            st.markdown(rec)
        return

    # 通用 dict 渲染（审核员输出中跳过已回流到活动创意/文案的修正版本）
    _skip_in_review = {'corrected_ideas', 'corrected_copies'}
    for k, v in d.items():
        if k in _skip_in_review:
            continue
        label = FIELD_LABELS.get(k, k)
        if isinstance(v, list):
            if v and isinstance(v[0], dict):
                st.markdown(f"**{label}**")
                for i, item in enumerate(v):
                    title_key = 'campaign_name' if 'campaign_name' in item else 'name'
                    item_title = item.get(title_key, f'#{i+1}')
                    st.markdown(f"&ensp;▸ **{item_title}**")
                    for ik, iv in item.items():
                        if ik in ('name', 'campaign_name'):
                            continue
                        sub_label = FIELD_LABELS.get(ik, ik)
                        if isinstance(iv, list):
                            st.markdown(f"&ensp;&ensp;&ensp;*{sub_label}*")
                            for si in iv:
                                st.markdown(f"&ensp;&ensp;&ensp;&ensp;• {si}")
                        elif isinstance(iv, dict):
                            st.markdown(f"&ensp;&ensp;&ensp;*{sub_label}*")
                            _render_nested_dict(iv, indent=4)
                        else:
                            st.markdown(f"&ensp;&ensp;&ensp;**{sub_label}**")
                            st.markdown(f"&ensp;&ensp;&ensp;{iv}")
            else:
                st.markdown(f"**{label}**")
                for item in v:
                    st.markdown(f"&ensp;▸ {item}")
        elif isinstance(v, bool):
            if v:
                st.markdown(f"**{label}** &ensp;:green[✅ 通过]")
            else:
                st.markdown(f"**{label}** &ensp;:orange[❌ 未通过]")
        elif isinstance(v, dict):
            st.markdown(f"**{label}**")
            _render_nested_dict(v, indent=1)
        else:
            st.markdown(f"**{label}**")
            st.markdown(str(v))


def _render_nested_dict(d: dict, indent: int = 1):
    """渲染嵌套 dict（非顶层）。"""
    prefix = '&ensp;' * (indent * 2)
    for k, v in d.items():
        sub_label = FIELD_LABELS.get(k, k)
        if isinstance(v, list):
            st.markdown(f"{prefix}*{sub_label}*")
            for item in v:
                st.markdown(f"{prefix}&ensp;• {item}")
        else:
            st.markdown(f"{prefix}**{sub_label}**")
            st.markdown(f"{prefix}{v}")


# ---- LLM 初始化 ----
@st.cache_resource
def init_llm():
    main.init_model()


# ---- 同步 Queue（侧边栏之前，保证对话列表第一时间更新） ----
_drain_queues()

# ===================== 侧边栏 =====================
with st.sidebar:
    st.title("🚀 MarketCrew")

    if st.button("➕ 新建对话", use_container_width=True, type="primary"):
        st.session_state.current_conv = None
        st.session_state.agent_outputs = []
        st.session_state._completed_outputs = None
        st.session_state.execution_phase = 'input'
        st.rerun()

    st.divider()
    st.caption(f"历史对话 · {len(st.session_state.conversations)} 个")

    if not st.session_state.conversations:
        st.caption("暂无历史对话")

    for conv in st.session_state.conversations:
        date_str = conv.get('created_at', '')[:10] if conv.get('created_at') else ''
        c1, c2 = st.columns([5, 1])
        with c1:
            if st.button(conv['project_name'][:22],
                         key=f"open_{conv['filename']}",
                         use_container_width=True, help=f"创建于 {date_str}"):
                data = load_conversation(conv['filename'])
                if data:
                    st.session_state.current_conv = data
                    st.session_state.agent_outputs = data.get('agent_outputs', [])
                    st.session_state._completed_outputs = None
                    st.session_state.execution_phase = 'input'
                    st.rerun()
        with c2:
            if st.button("🗑", key=f"del_{conv['filename']}", help="删除"):
                delete_conversation(conv['filename'])
                st.session_state.conversations = list_conversations()
                if st.session_state.current_conv and \
                   st.session_state.current_conv.get('filename') == conv['filename']:
                    st.session_state.current_conv = None
                    st.session_state.agent_outputs = []
                st.rerun()

# ===================== 主区域 =====================

st.markdown("## MarketCrew")
st.caption("虚拟营销团队：项目经理 → 市场分析师 → 营销战略师 → 内容创作师 → 内容审核员")

# ---- 历史对话提示 ----
if st.session_state.current_conv:
    project = st.session_state.current_conv.get('project_name', '历史对话')
    created = st.session_state.current_conv.get('created_at', '')
    st.info(f"📁 正在查看 **{project}**（{created}）")

# ---- Agent 输出（历史查看） ----
if st.session_state.agent_outputs and st.session_state.execution_phase == 'input':
    st.subheader("分析报告")
    cols = st.columns(2)
    for i, item in enumerate(st.session_state.agent_outputs):
        with cols[i % 2]:
            render_agent_output(item)

# ---- 运行中 ----
if st.session_state.execution_phase == 'running':
    elapsed = int(time.time() - st.session_state.runner_start_time)

    if elapsed > TIMEOUT_SECONDS:
        result_queue.put({
            'phase': 'timeout',
            'agent_outputs': [],
            'error_msg': f"执行超时（超过 {TIMEOUT_SECONDS // 60} 分钟）",
        })
        st.rerun()

    completed = len(st.session_state.progress)
    total_phases = len(PROGRESS_PHASES)
    pct = completed / total_phases if total_phases else 0

    st.subheader("团队协作中")
    st.caption(f"已完成 {completed}/{total_phases}  ·  {elapsed // 60} 分 {elapsed % 60} 秒")
    st.progress(pct)

    cols = st.columns(3)
    for i, (agent_key, _) in enumerate(PROGRESS_PHASES):
        col = cols[i % 3]
        icon = AGENT_ICONS.get(agent_key, '')
        name = AGENT_NAMES.get(agent_key, agent_key)
        if agent_key in st.session_state.progress:
            col.markdown(f"""
            <div class="phase-box phase-done">{icon}  {name} ✓</div>
            """, unsafe_allow_html=True)
        elif i == completed:
            col.markdown(f"""
            <div class="phase-box phase-active">{icon}  {name} ···</div>
            """, unsafe_allow_html=True)
        else:
            col.markdown(f"""
            <div class="phase-box phase-pending">{icon}  {name}</div>
            """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("终止执行", type="secondary", use_container_width=True):
            _clear_queues()
            st.session_state.execution_phase = 'input'
            st.session_state.agent_outputs = []
            st.rerun()

    time.sleep(3)
    st.rerun()

# ---- 完成 ----
if st.session_state.execution_phase == 'done':
    if st.session_state.get('_saved_docx'):
        project_name = st.session_state.get('_last_project_name', '未命名项目')
        try:
            docx_path = generate_program_docx(project_name, st.session_state.agent_outputs)
            st.success(f"方案文档已保存：`{docx_path}`")
        except Exception as e:
            st.warning(f"方案文档生成失败: {e}")
        st.session_state._saved_docx = False

    st.balloons()
    st.session_state.agent_outputs = []
    st.session_state.execution_phase = 'input'

# ---- 超时 ----
if st.session_state.execution_phase == 'timeout':
    st.error(f"⏰ {st.session_state.error_msg}")
    st.session_state.agent_outputs = []
    if st.button("🔙 返回"):
        st.session_state.execution_phase = 'input'
        st.rerun()

# ---- 错误 ----
if st.session_state.execution_phase == 'error':
    st.error(f"❌ 执行出错: {st.session_state.error_msg}")
    st.session_state.agent_outputs = []
    if st.button("🔙 返回"):
        st.session_state.execution_phase = 'input'
        st.rerun()

# ===================== 输入区 =====================
st.divider()

if st.session_state.execution_phase == 'input':
    completed_outputs = st.session_state.get('_completed_outputs', None)

    st.subheader("输入营销需求")

    with st.form("input_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            project_name = st.text_input(
                "项目名称",
                placeholder="例如：EMQX 营销方案",
            )
        with c2:
            uploaded_files = st.file_uploader(
                "上传参考文件（可选 .txt / .pdf / .docx）",
                type=['txt', 'pdf', 'docx'],
            )
        project_description = st.text_area(
            "项目描述",
            placeholder="描述产品背景、目标客户、营销需求等……\n\n示例：EMQX 是一款开源 MQTT 消息中间件，需要针对工业物联网领域制定营销推广方案。",
            height=100,
        )

        submitted = st.form_submit_button("开始分析", use_container_width=True, type="primary")

        if submitted:
            if not project_name.strip() or not project_description.strip():
                st.error("请填写项目名称和项目描述")
            else:
                init_llm()

                uploaded_contents = []
                if uploaded_files:
                    content = parse_uploaded_file(uploaded_files)
                    uploaded_contents.append(content)

                st.session_state._last_project_name = project_name.strip()
                st.session_state._last_project_desc = project_description.strip()
                st.session_state._last_uploaded = uploaded_contents
                st.session_state._completed_outputs = None

                start_execution(
                    project_name.strip(),
                    project_description.strip(),
                    uploaded_contents,
                )
                st.rerun()

    if completed_outputs:
        st.divider()
        st.subheader("分析报告")
        cols = st.columns(2)
        for i, item in enumerate(completed_outputs):
            with cols[i % 2]:
                render_agent_output(item)
        st.session_state._completed_outputs = None
