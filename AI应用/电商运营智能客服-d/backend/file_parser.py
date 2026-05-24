"""
企业级文件解析器：支持 TXT、PDF、DOCX、CSV、Markdown
PDF 解析优先 pdfplumber，失败时自动切换 PaddleOCR（扫描件支持）
"""
import io
import csv

# ---------- PDF 解析（含 OCR fallback） ----------
def parse_pdf(content: bytes) -> str:
    import pdfplumber

    # 第一步：尝试 pdfplumber 直接提取文字
    text_parts = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n".join(text_parts).strip()
    if len(full_text) > 10:          # 有效文字量足够，直接返回
        return full_text

    # 第二步：无文字或极少文字 -> OCR 扫描件
    try:
        from paddleocr import PaddleOCR
        from PIL import Image
    except ImportError:
        return "[错误] 需要 OCR 但未安装 PaddleOCR，请执行：pip install paddleocr paddlepaddle"

    ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
    ocr_texts = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            img = page.to_image(resolution=200)
            pil_img = img.original.convert('RGB')
            result = ocr.predict(pil_img)
            if result:
                page_lines = [
                    item['rec_text'] for item in result
                    if isinstance(item, dict) and item.get('rec_text')
                ]
                ocr_texts.append("\n".join(page_lines))

    ocr_full = "\n".join(ocr_texts).strip()
    return ocr_full if ocr_full else full_text   # 回退到空字符串

# ---------- 其他格式解析 ----------
def parse_txt(content: bytes) -> str:
    return content.decode("utf-8")

def parse_md(content: bytes) -> str:
    return content.decode("utf-8")

def parse_docx(content: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(content))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)

def parse_csv(content: bytes) -> str:
    decoded = content.decode("utf-8")
    reader = csv.reader(io.StringIO(decoded))
    rows = list(reader)
    if not rows:
        return ""
    lines = [" | ".join(row) for row in rows]
    return "\n".join(lines)

# ---------- 统一入口 ----------
def parse_file(filename: str, content: bytes) -> str:
    """根据文件扩展名调用对应解析器，返回文本"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return parse_pdf(content)
    elif ext == "docx":
        return parse_docx(content)
    elif ext == "csv":
        return parse_csv(content)
    elif ext in ("txt", "md"):
        return parse_txt(content)
    else:
        raise ValueError(f"不支持的文件类型: {ext}")