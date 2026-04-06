from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class PipelineResponse(BaseModel):
    """Метаданные ответа пайплайна (передаются в заголовках FileResponse)."""

    docx_filename: str
    input_tokens: int
    output_tokens: int
    tavily_requests: int


class SectionName(str, Enum):
    """Доступные секции для генерации."""
    info_from_pdf = "1_info_from_pdf"
    market_analyze = "2_market_analyze"
    competitors_analyze = "3_competitors_analyze"
    product_analyze = "4_product_analyze"
    team_analyze = "5_team_analyze"
    final_verdict = "6_final_verdict"


# Маппинг секции -> файл промпта
SECTION_PROMPT_MAP: dict[SectionName, str] = {
    SectionName.info_from_pdf: "1_info_from_pdf_prompt.md",
    SectionName.market_analyze: "2_market_analyze_prompt.md",
    SectionName.competitors_analyze: "3_competitors_analyze_prompt.md",
    SectionName.product_analyze: "4_product_analyze_prompt.md",
    SectionName.team_analyze: "5_team_analyze_prompt.md",
    SectionName.final_verdict: "6_final_verdict_prompt.md",
}
