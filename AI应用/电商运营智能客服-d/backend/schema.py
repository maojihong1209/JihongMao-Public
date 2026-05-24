from pydantic import BaseModel
from typing import Literal, Optional

class AIResponse(BaseModel):
    type: Literal["text", "order_card", "human_tip", "comparison_card"]
    content: str
    complaint_level: Optional[str] = None  # "低"/"中"/"高"
    complaint_type: Optional[str] = None   # "物流"/"质量"/"服务态度"/"其他"

class ChatOutput(BaseModel):
    session_id: str
    user_id: str
    intent: str
    input_text: str
    ai_response: AIResponse