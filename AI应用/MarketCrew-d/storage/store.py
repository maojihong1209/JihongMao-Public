# 标准库
import os
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT_HISTORY_DIR = os.path.join(BASE_DIR, "chat_history")


def _ensure_dir():
    os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)


def _extract_project_keyword(project_description: str) -> str:
    """从项目描述中提取关键词用作文件名。"""
    text = project_description[:300].strip()
    # 匹配英文关键词
    eng_matches = re.findall(r'[A-Za-z]{2,}', text)
    stop_words = {'http', 'https', 'com', 'www', 'org', 'cn', 'zh', 'the', 'and', 'for', 'are'}
    eng_keywords = [w for w in eng_matches if any(c.isupper() for c in w) and w.lower() not in stop_words]
    if eng_keywords:
        return eng_keywords[0][:30]
    # 提取中文字符
    cn_chars = re.findall(r'[一-鿿]+', text)
    cn_text = ''.join(cn_chars)
    if cn_text:
        return cn_text[:8]
    return "未命名项目"


def generate_filename(project_name: str) -> str:
    """生成对话文件名：{YYYYMMDD}_{项目名}.json"""
    date_str = datetime.now().strftime("%Y%m%d")
    safe_name = re.sub(r'[\\/:*?"<>|]', '', project_name)[:30]
    return f"{date_str}_{safe_name}.json"


def generate_project_name(project_name: str) -> str:
    """返回项目名称，用于 market_program 文件名和显示。"""
    return re.sub(r'[\\/:*?"<>|]', '', project_name)[:30]


def save_conversation(filename: str, conv_data: Dict[str, Any]):
    """保存对话数据到 chat_history/{filename}。"""
    _ensure_dir()
    filepath = os.path.join(CHAT_HISTORY_DIR, filename)
    conv_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(conv_data, f, ensure_ascii=False, indent=2)


def load_conversation(filename: str) -> Optional[Dict[str, Any]]:
    """从 chat_history/{filename} 加载对话数据。"""
    filepath = os.path.join(CHAT_HISTORY_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_conversations() -> List[Dict[str, str]]:
    """列出所有历史对话的元数据。"""
    _ensure_dir()
    conversations = []
    for fname in sorted(os.listdir(CHAT_HISTORY_DIR), reverse=True):
        if fname.endswith('.json'):
            filepath = os.path.join(CHAT_HISTORY_DIR, fname)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                conversations.append({
                    'filename': fname,
                    'project_name': data.get('project_name', fname),
                    'created_at': data.get('created_at', ''),
                    'updated_at': data.get('updated_at', ''),
                })
            except Exception:
                conversations.append({
                    'filename': fname,
                    'project_name': fname.replace('.json', ''),
                    'created_at': '',
                    'updated_at': '',
                })
    return conversations


def delete_conversation(filename: str) -> bool:
    """删除指定的对话文件。"""
    filepath = os.path.join(CHAT_HISTORY_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False
