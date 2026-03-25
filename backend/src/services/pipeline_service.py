"""
Сервисный слой для пайплайна анализа pitch-deck.

Задача этого модуля — инкапсулировать сценарий обработки презентации
и предоставить единый интерфейс для HTTP‑роутов (FastAPI).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional
import json

import anyio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.interfaces import UserRepository, ReportRepository
from ..repositories.sqlalchemy_repos import SqlAlchemyUserRepository, SqlAlchemyReportRepository
from ..modules.interfaces import (
    ILogger,
    ISlidesExtractor,
    ILLMClient,
    ISearchClient,
    IMarkdownBuilder,
    IDocxConverter,
)
from ..modules.paths import (
    ensure_dirs,
    TMP_DIR,
    RESULT_DIR,
    REPORT_LOG_ROOT,
    TAVILY_ROOT,
)
from ..modules.slides_extractor_impl import PdfSlidesExtractor
from ..modules.llm_client_impl import DefaultLLMClient, LLMConnectionError
from ..modules.search_client_impl import TavilySearchClient
from ..modules.markdown_builder_impl import MarkdownBuilderService
from ..modules.docx_converter_impl import DocxConverterService
from ..modules.logging_impl import default_logger


class PipelineService:
    """
    Сервис пайплайна.
    """

    def __init__(
        self,
        db: AsyncSession,
        user_repo: Optional[UserRepository] = None,
        report_repo: Optional[ReportRepository] = None,
        logger: Optional[ILogger] = None,
        slides_extractor: Optional[ISlidesExtractor] = None,
        llm_client: Optional[ILLMClient] = None,
        search_client: Optional[ISearchClient] = None,
        markdown_builder: Optional[IMarkdownBuilder] = None,
        docx_converter: Optional[IDocxConverter] = None,
    ) -> None:
        self.db = db
        self.user_repo: UserRepository = user_repo or SqlAlchemyUserRepository(db)
        self.report_repo: ReportRepository = report_repo or SqlAlchemyReportRepository(db)
        self.logger: ILogger = logger or default_logger
        self.slides_extractor: ISlidesExtractor = slides_extractor or PdfSlidesExtractor()
        self.llm_client: ILLMClient = llm_client or DefaultLLMClient()
        self.search_client: ISearchClient = search_client or TavilySearchClient()
        self.markdown_builder: IMarkdownBuilder = markdown_builder or MarkdownBuilderService()
        self.docx_converter: IDocxConverter = docx_converter or DocxConverterService()

    def _run_full_pipeline_sync(
        self,
        pdf_path: Path,
        presentation_dir: str,
        user_label: Optional[str] = None,
    ) -> Tuple[Path, Dict[str, int]]:
        """
        Синхронная реализация полного пайплайна.
        """
        ensure_dirs()

        stats: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "tavily_requests": 0}

        md_path = TMP_DIR / f"{presentation_dir}.md"
        docx_path = RESULT_DIR / f"{presentation_dir}.docx"

        self.logger.log("PIPELINE", f"Start full pipeline for '{presentation_dir}'", user_label)

        report_dir = REPORT_LOG_ROOT / presentation_dir
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "sections").mkdir(parents=True, exist_ok=True)
        self.logger.log("REPORTLOG", f"Report log directory: {report_dir}", user_label)

        # Этап 1: извлечение слайдов через интерфейс ISlidesExtractor
        from ..modules.paths import SLIDES_ROOT

        slides_dir = SLIDES_ROOT / presentation_dir
        slides_dir.mkdir(parents=True, exist_ok=True)

        self.logger.log("SLIDES", f"Start processing PDF: {pdf_path}", user_label)
        self.logger.log("SLIDES", f"Target directory: {slides_dir}", user_label)
        try:
            image_paths = self.slides_extractor.pdf_to_images(pdf_path=pdf_path, output_dir=slides_dir)
        except Exception as e:
            self.logger.log("SLIDES", f"Error while processing slides for '{pdf_path}': {e}", user_label)
            raise
        self.logger.log("SLIDES", "Slide processing completed successfully", user_label)

        self.logger.log("PIPELINE", f"Starting Qwen for '{presentation_dir}' ({len(image_paths)} slides)", user_label)
        qwen_text = self.llm_client.extract_information_from_images(
            image_paths=image_paths,
            presentation_dir=presentation_dir,
            stats=stats,
        )
        self.logger.log("PIPELINE", f"Qwen finished for '{presentation_dir}' ({len(qwen_text)} chars)", user_label)

        self.logger.log("PIPELINE", f"Starting Tavily query generation for '{presentation_dir}'", user_label)
        tavily_queries_by_category = self.llm_client.generate_tavily_queries(
            qwen_text=qwen_text,
            presentation_dir=presentation_dir,
            stats=stats,
        )
        self.logger.log("PIPELINE", f"Tavily query generation completed: {len(tavily_queries_by_category)} categories", user_label)
        try:
            (report_dir / "query_generation_summary.json").write_text(
                json.dumps(
                    {
                        "presentation_dir": presentation_dir,
                        "query_generation_dir": str(TAVILY_ROOT / "query_generation" / presentation_dir),
                        "categories": list(tavily_queries_by_category.keys()),
                        "total_queries": sum(len(v) for v in tavily_queries_by_category.values()),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            self.logger.log("REPORTLOG", f"Query generation summary saved: {report_dir / 'query_generation_summary.json'}", user_label)
        except Exception as e:
            self.logger.log("REPORTLOG", f"Failed to write query generation summary: {e}", user_label)

        self.logger.log("PIPELINE", "Starting DeepSeek sections 1-5", user_label)
        section_texts, intermediate_md = self.llm_client.run_sections(
            qwen_text=qwen_text,
            presentation_dir=presentation_dir,
            tavily_queries_by_category=tavily_queries_by_category,
            stats=stats,
        )

        self.logger.log("PIPELINE", "Starting final verdict (section 6)", user_label)
        final_text = self.llm_client.run_final_verdict(
            intermediate_md=intermediate_md,
            presentation_dir=presentation_dir,
            stats=stats,
        )

        full_md = self.markdown_builder.build_full_markdown(section_texts=section_texts, final_text=final_text)
        md_path.write_text(full_md, encoding="utf-8")
        self.logger.log("REPORT", f"Markdown saved to: {md_path} ({len(full_md)} chars)", user_label)

        self.logger.log("REPORT", f"Converting MD to DOCX: {md_path} -> {docx_path}", user_label)
        self.docx_converter.convert_md_to_docx(md_path=md_path, docx_path=docx_path)
        docx_size = docx_path.stat().st_size if docx_path.exists() else 0
        self.logger.log("REPORT", f"DOCX saved to: {docx_path} ({docx_size} bytes)", user_label)
        self.logger.log("REPORT", f"Pipeline completed: report ready at {docx_path}", user_label)

        try:
            section_names = [
                "1_info_from_pdf",
                "2_market_analyze",
                "3_competitors_analyze",
                "4_product_analyze",
                "5_team_analyze",
                "final_verdict",
            ]
            report_log_path = report_dir / "report_log.json"
            summary = {
                "presentation_dir": presentation_dir,
                "paths": {
                    "pdf_path": str(pdf_path),
                    "md_path": str(md_path),
                    "docx_path": str(docx_path),
                },
                "sizes": {
                    "md_chars": len(full_md),
                    "docx_bytes": docx_path.stat().st_size if docx_path.exists() else 0,
                },
                "tavily": {
                    "query_generation_dir": str(TAVILY_ROOT / "query_generation" / presentation_dir),
                    "per_section_root": str(TAVILY_ROOT),
                },
                "sections": {
                    name: str((report_dir / "sections" / f"{name}.json"))
                    for name in section_names
                },
            }
            report_log_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            self.logger.log("REPORTLOG", f"Unified report log saved: {report_log_path}", user_label)
        except Exception as e:
            self.logger.log("REPORTLOG", f"Failed to write unified report log: {e}", user_label)

        return docx_path, stats

    async def run_full_pipeline(
        self,
        pdf_path: Path,
        presentation_dir: str,
        user_label: Optional[str] = None,
        telegram_id: Optional[int] = None,
        username: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Tuple[Path, Dict[str, int]]:
        """
        Запуск полного пайплайна: PDF -> отчёт DOCX + статистика.
        """
        try:
            docx_path, stats = await anyio.to_thread.run_sync(
                self._run_full_pipeline_sync,
                pdf_path,
                presentation_dir,
                user_label,
            )
        except LLMConnectionError as e:
            raise HTTPException(status_code=503, detail=f"Ошибка соединения с LLM-провайдером: {e}") from e

        report_log_path = str(REPORT_LOG_ROOT / presentation_dir / "report_log.json")
        await self.report_repo.create_report(
            presentation_dir=presentation_dir,
            user_id=user_id,
            pdf_path=str(pdf_path),
            docx_path=str(docx_path),
            report_log_path=report_log_path,
            input_tokens=stats.get("input_tokens", 0),
            output_tokens=stats.get("output_tokens", 0),
            tavily_requests=stats.get("tavily_requests", 0),
        )

        if user_id is not None:
            await self.user_repo.add_token_stats(
                user_id=user_id,
                input_tokens=stats.get("input_tokens", 0),
                output_tokens=stats.get("output_tokens", 0),
                tavily_requests=stats.get("tavily_requests", 0),
            )

        return docx_path, stats


    def _run_single_section_sync(
        self,
        pdf_path: Path,
        presentation_dir: str,
        section: str,
        user_label: Optional[str] = None,
    ) -> Tuple[Path, Dict[str, int]]:
        """
        Синхронная генерация одной секции отчёта.
        section — значение SectionName (например '2_market_analyze').
        """
        from ..schemas.pipeline import SectionName, SECTION_PROMPT_MAP

        ensure_dirs()
        stats: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "tavily_requests": 0}

        section_enum = SectionName(section)
        prompt_filename = SECTION_PROMPT_MAP[section_enum]

        md_path = TMP_DIR / f"{presentation_dir}_{section}.md"
        docx_path = RESULT_DIR / f"{presentation_dir}_{section}.docx"

        self.logger.log("PIPELINE", f"Single section '{section}' start for '{presentation_dir}'", user_label)

        # Этап 1: слайды
        from ..modules.paths import SLIDES_ROOT
        slides_dir = SLIDES_ROOT / presentation_dir
        slides_dir.mkdir(parents=True, exist_ok=True)
        image_paths = self.slides_extractor.pdf_to_images(pdf_path=pdf_path, output_dir=slides_dir)
        self.logger.log("SLIDES", f"Extracted {len(image_paths)} slides", user_label)

        # Этап 2: Qwen
        qwen_text = self.llm_client.extract_information_from_images(
            image_paths=image_paths,
            presentation_dir=presentation_dir,
            stats=stats,
        )
        self.logger.log("PIPELINE", f"Qwen done ({len(qwen_text)} chars)", user_label)

        if section_enum == SectionName.final_verdict:
            # Для финального вердикта нужны секции 2-5 как intermediate_md
            # Генерируем их сначала (без Tavily для простоты)
            section_prompts = [
                "2_market_analyze_prompt.md",
                "3_competitors_analyze_prompt.md",
                "4_product_analyze_prompt.md",
                "5_team_analyze_prompt.md",
            ]
            parts = []
            for pf in section_prompts:
                text = self.llm_client.run_section(
                    prompt_filename=pf,
                    qwen_text=qwen_text,
                    presentation_dir=presentation_dir,
                    stats=stats,
                )
                parts.append(text)
            intermediate_md = "\n\n\n".join(parts)
            section_text = self.llm_client.run_final_verdict(
                intermediate_md=intermediate_md,
                presentation_dir=presentation_dir,
                stats=stats,
            )
        else:
            # Tavily поиск для секции
            tavily_queries_by_category = self.llm_client.generate_tavily_queries(
                qwen_text=qwen_text,
                presentation_dir=presentation_dir,
                stats=stats,
            )
            search_results = self.llm_client._integrate_tavily_search(  # type: ignore[attr-defined]
                prompt_filename=prompt_filename,
                qwen_text=qwen_text,
                tavily_queries_by_category=tavily_queries_by_category,
                presentation_dir=presentation_dir,
                stats=stats,
            )
            section_text = self.llm_client.run_section(
                prompt_filename=prompt_filename,
                qwen_text=qwen_text,
                presentation_dir=presentation_dir,
                search_results=search_results,
                stats=stats,
            )

        md_path.write_text(section_text, encoding="utf-8")
        self.logger.log("REPORT", f"Section markdown saved: {md_path}", user_label)

        self.docx_converter.convert_md_to_docx(md_path=md_path, docx_path=docx_path)
        self.logger.log("REPORT", f"Section DOCX saved: {docx_path}", user_label)

        return docx_path, stats

    async def run_single_section(
        self,
        pdf_path: Path,
        presentation_dir: str,
        section: str,
        user_label: Optional[str] = None,
        telegram_id: Optional[int] = None,
        username: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Tuple[Path, Dict[str, int]]:
        """
        Генерация одной выбранной секции отчёта.
        """
        try:
            docx_path, stats = await anyio.to_thread.run_sync(
                self._run_single_section_sync,
                pdf_path,
                presentation_dir,
                section,
                user_label,
            )
        except LLMConnectionError as e:
            raise HTTPException(status_code=503, detail=f"Ошибка соединения с LLM-провайдером: {e}") from e

        report_log_path = str(REPORT_LOG_ROOT / presentation_dir / "report_log.json")
        await self.report_repo.create_report(
            presentation_dir=f"{presentation_dir}_{section}",
            user_id=user_id,
            pdf_path=str(pdf_path),
            docx_path=str(docx_path),
            report_log_path=report_log_path,
            input_tokens=stats.get("input_tokens", 0),
            output_tokens=stats.get("output_tokens", 0),
            tavily_requests=stats.get("tavily_requests", 0),
        )

        if user_id is not None:
            await self.user_repo.add_token_stats(
                user_id=user_id,
                input_tokens=stats.get("input_tokens", 0),
                output_tokens=stats.get("output_tokens", 0),
                tavily_requests=stats.get("tavily_requests", 0),
            )

        return docx_path, stats


def get_pipeline_service(db: AsyncSession) -> PipelineService:
    """
    Фабрика для использования с FastAPI Depends (инъекция зависимостей).
    """
    return PipelineService(db=db)
