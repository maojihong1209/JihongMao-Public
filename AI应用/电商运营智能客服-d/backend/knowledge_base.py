import io, csv, hashlib
from datetime import datetime

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

import config_data as config


def _split_csv_rows(data: str) -> list[str]:
    """CSV 按行切分，每行格式化为 '列名: 值' 的易读文本。"""
    reader = csv.DictReader(io.StringIO(data))
    rows = []
    for row in reader:
        parts = [f"{k}: {v}" for k, v in row.items() if v]
        if parts:
            rows.append(" | ".join(parts))
    return rows


class KnowledgeBaseService:

    def __init__(self):
        self.chroma = Chroma(
            collection_name=config.collection_name,
            persist_directory=config.persist_directory,
            embedding_function=DashScopeEmbeddings(model=config.embedding_model_name),
        )

        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
            length_function=len,
        )

        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=config.markdown_headers,
            strip_headers=False,
        )

    # ---- 统一入口 ----
    def upload_str(self, data: str, filename: str, file_ext: str) -> tuple[int, str, str]:
        """按文件类型选择切分路线，写入 ChromaDB。
        返回 (chunk_count, hash_hex, split_method)。
        """
        hash_hex = hashlib.sha256(data.encode("utf-8")).hexdigest()

        ext = file_ext.lower()
        if ext == "csv":
            chunks, split_method = self._split_csv(data, filename)
        elif ext == "md":
            chunks, split_method = self._split_markdown(data, filename)
        else:
            chunks, split_method = self._split_recursive(data, filename)

        if not chunks:
            return 0, hash_hex, split_method

        total = len(chunks)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadatas = [
            {
                "source": filename,
                "chunk_index": i,
                "total_chunks": total,
                "create_time": timestamp,
                "operator": "人工客服",
                "split_method": split_method,
                **({k: v for k, v in (chunks[i].metadata or {}).items() if k.startswith("h")} if hasattr(chunks[i], "metadata") else {}),
            }
            for i in range(total)
        ]
        texts = [d.page_content if hasattr(d, "page_content") else str(d) for d in chunks]

        self.chroma.add_texts(texts, metadatas=metadatas)
        return total, hash_hex, split_method

    # ---- 各路线 ----

    def _split_recursive(self, data: str, filename: str) -> tuple[list, str]:
        if len(data) > config.chunk_size:
            docs = self.recursive_splitter.create_documents([data])
        else:
            from langchain_core.documents import Document
            docs = [Document(page_content=data)]
        return docs, "recursive"

    def _split_markdown(self, data: str, filename: str) -> tuple[list, str]:
        docs = self.md_splitter.split_text(data)
        if not docs:
            # 无标题结构时降级为递归切分
            return self._split_recursive(data, filename)
        return docs, "markdown_header"

    def _split_csv(self, data: str, filename: str) -> tuple[list, str]:
        from langchain_core.documents import Document
        rows = _split_csv_rows(data)
        if not rows:
            return [], "csv_row"
        docs = [Document(page_content=row) for row in rows]
        return docs, "csv_row"

    # ---- 查询 ----
    def get_chunks_by_source(self, filename: str) -> list[dict]:
        result = self.chroma.get(where={"source": filename})
        chunks = []
        if result and result["ids"]:
            for i, cid in enumerate(result["ids"]):
                chunks.append({
                    "id": cid,
                    "content": result["documents"][i] if result["documents"] else "",
                    "chunk_index": result["metadatas"][i].get("chunk_index", i) if result["metadatas"] else i,
                })
        return chunks

    # ---- 删除 ----
    def delete_by_source(self, filename: str) -> int:
        result = self.chroma.get(where={"source": filename})
        count = len(result["ids"]) if result and result["ids"] else 0
        if count > 0:
            self.chroma.delete(where={"source": filename})
        return count

    def delete_chunk(self, chunk_id: str) -> None:
        self.chroma.delete(ids=[chunk_id])

    # ---- 统计 ----
    @property
    def total_chunks(self) -> int:
        return self.chroma._collection.count()
