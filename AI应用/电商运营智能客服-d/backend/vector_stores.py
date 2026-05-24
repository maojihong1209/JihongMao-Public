import os, threading
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnablePassthrough, RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi
import jieba
from dotenv import load_dotenv
from file_history_store import get_history
import config_data as config

load_dotenv()


class VectorStoreService:
    def __init__(self, embedding):
        self.embedding = embedding
        self.reranker = None  # CrossEncoder 待启用

        self.vector_store = Chroma(
            collection_name=config.collection_name,
            embedding_function=self.embedding,
            persist_directory=config.persist_directory,
        )

        self.bm25_docs = None
        self.bm25_texts = None
        self.bm25_index = None
        self.cached_ids = None
        self.bm25_lock = threading.Lock()

    def build_bm25(self):
        all_data = self.vector_store.get(include=["documents", "metadatas"])
        all_ids = all_data["ids"]
        all_docs = all_data["documents"]
        all_metas = all_data["metadatas"]

        if not all_ids:
            self.bm25_docs = []
            self.bm25_texts = []
            self.bm25_index = None
            self.cached_ids = []
            return

        if self.cached_ids is not None and self.cached_ids == all_ids:
            return

        with self.bm25_lock:
            # 双重检查，避免重复重建
            if self.cached_ids is not None and self.cached_ids == all_ids:
                return
            self.cached_ids = list(all_ids)
            self.bm25_docs = [
                Document(page_content=text, metadata=meta)
                for text, meta in zip(all_docs, all_metas)
            ]
            self.bm25_texts = list(all_docs)
            tokenized_corpus = [list(jieba.cut(text)) for text in all_docs]
            self.bm25_index = BM25Okapi(tokenized_corpus)

    def bm25_search(self, query, top_k):
        self.build_bm25()
        if not self.bm25_texts or self.bm25_index is None:
            return []
        tokenized_query = list(jieba.cut(query))
        scores = self.bm25_index.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [self.bm25_docs[i] for i in top_indices]

    def get_retriever(self):
        final_k = config.similarity_number
        vector_k = final_k * 2
        bm25_k = final_k * 2

        def hybrid_retriever(query):
            vector_docs = self.vector_store.similarity_search(query, k=vector_k)
            bm25_docs = self.bm25_search(query, bm25_k)

            doc_id_map = {}
            rrf_scores = {}

            def add_to_rrf(docs):
                for rank, doc in enumerate(docs):
                    doc_id = doc.page_content.strip()
                    if doc_id not in doc_id_map:
                        doc_id_map[doc_id] = doc
                    rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (60 + rank + 1)

            add_to_rrf(vector_docs)
            add_to_rrf(bm25_docs)

            merged_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
            merged_docs = [doc_id_map[did] for did in merged_ids]

            if self.reranker is not None and len(merged_docs) > 1:
                pairs = [[query, doc.page_content] for doc in merged_docs]
                scores = self.reranker.predict(pairs)
                scored_docs = sorted(zip(scores, merged_docs), key=lambda x: x[0], reverse=True)
                return [doc for _, doc in scored_docs[:final_k]]
            return merged_docs[:final_k]

        return RunnableLambda(hybrid_retriever)


class RagService:
    def __init__(self):
        self.chat = ChatTongyi(
            model=config.chat_model_name,
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
        )

        self.vector_service = VectorStoreService(
            embedding=DashScopeEmbeddings(model=config.embedding_model_name)
        )

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", "以我提供的已知参考资料为主，简洁和专业的回答用户问题。参考资料:{context}"),
            ("system", "并且我提供用户的对话历史记录，如下："),
            MessagesPlaceholder("history"),
            ("user", "用户提问：{input}"),
        ])

        self.chain = self.build_chain()

    def build_chain(self):
        get_retriever = self.vector_service.get_retriever()

        def format_for_retriever(value: dict) -> str:
            return value["input"]

        def format_for_document(docs: list[Document]):
            if not docs:
                return "无相关参考资料"
            formatted_str = ""
            for doc in docs:
                formatted_str += f"文档片段：{doc.page_content}\n文档元数据：{doc.metadata}\n\n"
            return formatted_str

        def format_for_prompt_template(value):
            return {
                "input": value["input"]["input"],
                "context": value["context"],
                "history": value["input"]["history"],
            }

        chain = (
            {
                "input": RunnablePassthrough(),
                "context": RunnableLambda(format_for_retriever) | get_retriever | format_for_document,
            }
            | RunnableLambda(format_for_prompt_template) | self.prompt_template | self.chat | StrOutputParser()
        )

        return RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
        )


if __name__ == "__main__":
    import asyncio
    async def test():
        session_config = {"configurable": {"session_id": "user_001"}}
        res = await RagService().chain.ainvoke({"input": "体重160斤穿什么尺码衣服合适？"}, session_config)
        print(res)
    asyncio.run(test())
