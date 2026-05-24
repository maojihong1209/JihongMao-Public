import os, json, asyncio, logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from auth.database import engine, Base, get_db, AsyncSessionLocal
from auth.models import User, UserCreate, Token, KnowledgeFile
from auth.auth import get_password_hash, verify_password, create_access_token, get_current_user
import chat  # noqa: F401 — 注册 ChatMessage 模型
from knowledge_base import KnowledgeBaseService
from vector_stores import RagService
from intent_classifier import IntentClassifier
from agent import CustomerServiceAgent
from schema import ChatOutput
from file_parser import parse_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


async def init_db():
    from sqlalchemy import text
    async with engine.begin() as conn:
        # 确保 schema 存在
        for schema in ("information_db", "chat_db"):
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "user_001"


# 服务单例
kb_service = KnowledgeBaseService()
rag_service = RagService()
intent_classifier = IntentClassifier()
agent = CustomerServiceAgent(intent_classifier, rag_service, AsyncSessionLocal)


# ---- 认证路由 ----
@app.post("/register", response_model=Token)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    if len(user.password) < 6:
        raise HTTPException(400, "密码长度不能少于6位")
    if len(user.username.strip()) < 2:
        raise HTTPException(400, "用户名长度不能少于2位")

    from sqlalchemy import select
    result = await db.execute(select(User).where(User.username == user.username))
    if result.scalar_one_or_none():
        raise HTTPException(400, "用户名已存在")
    hashed = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed, role="user")
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    token = create_access_token(data={"sub": new_user.username})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/token", response_model=Token)
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(400, "用户名或密码错误")
    token = create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


# ---- 业务路由 ----
@app.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username}


@app.get("/sessions")
async def get_sessions(current_user: User = Depends(get_current_user)):
    from file_history_store import get_user_sessions_async
    return await get_user_sessions_async(AsyncSessionLocal, current_user.id)


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    if not session_id.startswith(f"{current_user.id}_{current_user.username}_"):
        raise HTTPException(403, "无权操作此会话")
    from file_history_store import delete_session_data_async
    await delete_session_data_async(session_id, AsyncSessionLocal)
    return {"status": "deleted"}


@app.put("/sessions/{session_id}/rename")
async def rename_session(
    session_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    # 仅允许重命名自己的会话
    if not session_id.startswith(f"{current_user.id}_{current_user.username}_"):
        raise HTTPException(403, "无权操作此会话")

    from file_history_store import set_session_title_async
    new_title = payload.get("title", "").strip()
    if not new_title:
        raise HTTPException(400, "标题不能为空")
    if len(new_title) > 50:
        raise HTTPException(400, "标题不能超过50字")
    await set_session_title_async(session_id, new_title)
    return {"status": "ok", "title": new_title}


@app.post("/chat")
async def chat(request: ChatRequest, current_user: User = Depends(get_current_user)):
    output = await agent.invoke(
        user_id=current_user.id,
        username=current_user.username,
        session_id=request.session_id,
        input_text=request.message,
    )
    return output.model_dump()


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: User = Depends(get_current_user)):
    async def event_stream():
        async for event in agent.stream(
            user_id=current_user.id,
            username=current_user.username,
            session_id=request.session_id,
            input_text=request.message,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/history/{session_id}")
async def get_history(session_id: str, current_user: User = Depends(get_current_user)):
    from file_history_store import get_chat_history_async
    try:
        messages = await get_chat_history_async(AsyncSessionLocal, session_id)
        return {"messages": messages}
    except Exception as e:
        logger.exception("获取历史失败")
        raise HTTPException(500, f"获取历史失败: {e}")


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    allowed_ext = ["txt", "pdf", "csv", "docx", "md"]
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed_ext:
        raise HTTPException(400, f"不支持的文件类型，仅支持: {', '.join(allowed_ext)}")

    content = await file.read()
    text = await asyncio.to_thread(parse_file, file.filename, content)
    chunk_count, file_hash = kb_service.upload_str(text, file.filename)

    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(KnowledgeFile).where(
                KnowledgeFile.file_hash == file_hash,
                KnowledgeFile.status == "active",
            )
        )
        if existing.scalar_one_or_none():
            # 已存在，回滚 ChromaDB 写入
            kb_service.delete_by_source(file.filename)
            raise HTTPException(400, "该文件内容已存在于知识库中")

        kf = KnowledgeFile(
            filename=file.filename,
            file_hash=file_hash,
            file_size=len(content),
            chunk_count=chunk_count,
            operator=current_user.username,
        )
        db.add(kf)
        await db.commit()

    return {"status": "success", "file_id": kf.id, "chunk_count": chunk_count}


# ---- 知识库管理路由 ----
@app.get("/kb/files")
async def list_kb_files(
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select, func
    async with AsyncSessionLocal() as db:
        total_query = await db.execute(
            select(func.count()).select_from(KnowledgeFile).where(KnowledgeFile.status == "active")
        )
        total = total_query.scalar() or 0

        result = await db.execute(
            select(KnowledgeFile)
            .where(KnowledgeFile.status == "active")
            .order_by(KnowledgeFile.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        files = result.scalars().all()

    return {
        "items": [
            {
                "id": f.id,
                "filename": f.filename,
                "file_size": f.file_size,
                "chunk_count": f.chunk_count,
                "status": f.status,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "operator": f.operator,
            }
            for f in files
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/kb/files/{file_id}")
async def get_kb_file_chunks(
    file_id: int,
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeFile).where(
                KnowledgeFile.id == file_id,
                KnowledgeFile.status == "active",
            )
        )
        kf = result.scalar_one_or_none()
        if not kf:
            raise HTTPException(404, "文件不存在")

    chunks = kb_service.get_chunks_by_source(kf.filename)
    return {
        "file": {
            "id": kf.id,
            "filename": kf.filename,
            "file_size": kf.file_size,
            "chunk_count": kf.chunk_count,
            "created_at": kf.created_at.isoformat() if kf.created_at else None,
        },
        "chunks": chunks,
    }


@app.delete("/kb/files/{file_id}")
async def delete_kb_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KnowledgeFile).where(KnowledgeFile.id == file_id))
        kf = result.scalar_one_or_none()
        if not kf:
            raise HTTPException(404, "文件不存在")

        # 软删除 DB 记录
        kf.status = "deleted"
        # 删除 ChromaDB 中所有 chunk
        deleted_count = kb_service.delete_by_source(kf.filename)
        await db.commit()

    return {"status": "deleted", "chunks_removed": deleted_count}


@app.delete("/kb/chunks/{chunk_id}")
async def delete_kb_chunk(
    chunk_id: str,
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    # 先获取元数据（删除后无法查询）
    all_data = kb_service.chroma.get(ids=[chunk_id])
    source = ""
    if all_data and all_data["metadatas"] and all_data["metadatas"][0]:
        source = all_data["metadatas"][0].get("source", "")

    kb_service.delete_chunk(chunk_id)

    if source:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(KnowledgeFile).where(
                    KnowledgeFile.filename == source,
                    KnowledgeFile.status == "active",
                )
            )
            kf = result.scalar_one_or_none()
            if kf and kf.chunk_count > 0:
                kf.chunk_count -= 1
                await db.commit()

    return {"status": "deleted"}
