import os, hashlib
from datetime import datetime
from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import config_data as config


class KnowledgeBaseService:
    """知识库服务 — 负责 ChromaDB 向量存储操作，文件元数据由 PostgreSQL 管理"""

    def __init__(self):
        os.makedirs(config.persist_directory, exist_ok=True)

        self.chroma = Chroma(
            collection_name=config.collection_name,
            persist_directory=config.persist_directory,
            embedding_function=DashScopeEmbeddings(model=config.embedding_model_name),
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
            length_function=len,
        )

    # ---- 上传 ----
    def upload_str(self, data: str, filename: str) -> tuple[int, str]:
        """切分文本并写入 ChromaDB，返回 (chunk_count, hash_hex)"""
        hash_hex = hashlib.sha256(data.encode("utf-8")).hexdigest()

        if len(data) > config.chunk_size:
            chunks = self.spliter.split_text(data)
        else:
            chunks = [data]

        total = len(chunks)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadatas = [
            {
                "source": filename,
                "chunk_index": i,
                "total_chunks": total,
                "create_time": timestamp,
                "operator": "人工客服",
            }
            for i in range(total)
        ]

        self.chroma.add_texts(chunks, metadatas=metadatas)
        return total, hash_hex

    # ---- 查询 ----
    def get_chunks_by_source(self, filename: str) -> list[dict]:
        """按 source 文件名获取所有 chunk"""
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
        """按 source 文件名删除所有 chunk，返回删除数量"""
        result = self.chroma.get(where={"source": filename})
        count = len(result["ids"]) if result and result["ids"] else 0
        if count > 0:
            self.chroma.delete(where={"source": filename})
        return count

    def delete_chunk(self, chunk_id: str) -> None:
        """删除单条 chunk"""
        self.chroma.delete(ids=[chunk_id])

    # ---- 统计 ----
    @property
    def total_chunks(self) -> int:
        return self.chroma._collection.count()
