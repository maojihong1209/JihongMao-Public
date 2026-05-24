# 标准库
from typing import List

# 第三方包
from pydantic import BaseModel, Field


class PMOutput(BaseModel):
    """项目经理输出"""
    requirement_analysis: str = Field(..., description="对用户需求的完整分析")
    task_breakdown: List[str] = Field(..., description="拆解后需要完成的子任务列表")
    key_guidance: str = Field(..., description="给下游Agent的关键指引")


class ResearchReport(BaseModel):
    """市场分析师输出"""
    market_overview: str = Field(..., description="市场概况")
    competitor_analysis: str = Field(..., description="竞品分析")
    audience_insights: str = Field(..., description="目标受众洞察")


class MarketStrategy(BaseModel):
    """营销战略师输出 — 3个备选方案（拍平结构，避免嵌套JSON失败）"""
    strategy_a_name: str = Field(..., description="方案A（稳健保守型）名称")
    strategy_a_tactics: List[str] = Field(..., description="方案A战术清单")
    strategy_a_channels: List[str] = Field(..., description="方案A渠道清单")
    strategy_a_kpis: List[str] = Field(..., description="方案A关键绩效指标")

    strategy_b_name: str = Field(..., description="方案B（创新突破型）名称")
    strategy_b_tactics: List[str] = Field(..., description="方案B战术清单")
    strategy_b_channels: List[str] = Field(..., description="方案B渠道清单")
    strategy_b_kpis: List[str] = Field(..., description="方案B关键绩效指标")

    strategy_c_name: str = Field(..., description="方案C（组合平衡型）名称")
    strategy_c_tactics: List[str] = Field(..., description="方案C战术清单")
    strategy_c_channels: List[str] = Field(..., description="方案C渠道清单")
    strategy_c_kpis: List[str] = Field(..., description="方案C关键绩效指标")

    recommendation: str = Field(..., description="最终推荐方案及理由")


class IdeaItem(BaseModel):
    """单个活动创意"""
    name: str = Field(..., description="活动创意名称")
    description: str = Field(..., description="活动创意说明")
    audience: str = Field(..., description="目标受众")
    channel: str = Field(..., description="推广渠道")


class CampaignIdea(BaseModel):
    """活动创意输出 — 3个创意"""
    ideas: List[IdeaItem] = Field(..., description="3个活动创意，覆盖不同渠道和受众")


class CopyItem(BaseModel):
    """单个活动文案"""
    campaign_name: str = Field(..., description="对应的活动创意名称")
    title: str = Field(..., description="文案标题")
    body: str = Field(..., description="文案正文")


class Copy(BaseModel):
    """文案输出 — 每活动一份"""
    copies: List[CopyItem] = Field(..., description="每个活动创意对应的营销文案")


class ReviewResult(BaseModel):
    """内容审核员输出"""
    approved: bool = Field(..., description="是否审核通过")
    issues_found: List[str] = Field(default_factory=list, description="发现的问题列表")
    revisions_made: List[str] = Field(default_factory=list, description="本次审核中修正的内容（改了什么，哪里改到哪里）")
    corrected_ideas: List[IdeaItem] = Field(default_factory=list, description="修正后的活动创意（完整输出）")
    corrected_copies: List[CopyItem] = Field(default_factory=list, description="修正后的营销文案（完整输出）")
    review_notes: str = Field(..., description="审核备注与建议")
