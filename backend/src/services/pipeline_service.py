"""
Сервисный слой для пайплайна анализа pitch-deck.

Задача этого модуля — инкапсулировать сценарий обработки презентации
и предоставить единый интерфейс для HTTP‑роутов (FastAPI).

Внутри пока используются функции из модуля `pipeline`, но при необходимости
их реализацию можно заменить, не трогая маршруты.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Optional
import json

import anyio
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
from ..modules.llm_client_impl import DefaultLLMClient
from ..modules.search_client_impl import TavilySearchClient
from ..modules.markdown_builder_impl import MarkdownBuilderService
from ..modules.docx_converter_impl import DocxConverterService
from ..modules.logging_impl import default_logger


class PipelineService:
    """
    Сервис пайплайна.

    В дальнейшем сюда можно внедрять зависимости (репозитории, клиенты внешних API)
    через конструктор. Сейчас он обёртывает существующую реализацию в `pipeline`.
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
        # Логгер и реализации интерфейсов пайплайна
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

        Логика перенесена из старого `pipeline.run_full_pipeline`, чтобы пайплайн жил в сервисном слое.
        """
        ensure_dirs()

        stats: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "tavily_requests": 0}

        def _log_user(component: str, message: str) -> None:
            if user_label:
                self.logger.log(component, f"[user={user_label}] {message}")
            else:
                self.logger.log(component, message)

        md_path = TMP_DIR / f"{presentation_dir}.md"
        docx_path = RESULT_DIR / f"{presentation_dir}.docx"

        _log_user("PIPELINE", f"Start full pipeline for '{presentation_dir}'")

        report_dir = REPORT_LOG_ROOT / presentation_dir
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "sections").mkdir(parents=True, exist_ok=True)
        _log_user("REPORTLOG", f"Report log directory: {report_dir}")

        # Этап 1: извлечение слайдов через интерфейс ISlidesExtractor
        from ..modules.paths import SLIDES_ROOT  # локальный импорт, чтобы избежать длинного списка сверху

        slides_dir = SLIDES_ROOT / presentation_dir
        slides_dir.mkdir(parents=True, exist_ok=True)

        self.logger.log("SLIDES", f"Start processing PDF: {pdf_path}")
        self.logger.log("SLIDES", f"Target directory: {slides_dir}")
        try:
            image_paths = self.slides_extractor.pdf_to_images(pdf_path=pdf_path, output_dir=slides_dir)
        except Exception as e:
            self.logger.log("SLIDES", f"Error while processing slides for '{pdf_path}': {e}")
            raise
        self.logger.log("SLIDES", "slide processing completed successfully")

        _log_user("PIPELINE", f"Starting Qwen for '{presentation_dir}' ({len(image_paths)} slides)")
        qwen_text = self.llm_client.extract_information_from_images(
            image_paths=image_paths,
            presentation_dir=presentation_dir
        )
        _log_user("PIPELINE", f"Qwen finished for '{presentation_dir}' ({len(qwen_text)} chars)")

        _log_user("PIPELINE", f"Starting Tavily query generation for '{presentation_dir}'")
        tavily_queries_by_category = self.llm_client.generate_tavily_queries(
            qwen_text=qwen_text,
            presentation_dir=presentation_dir,
            stats=stats
        )
        _log_user("PIPELINE", f"Tavily query generation completed: {len(tavily_queries_by_category)} categories")
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
            _log_user(
                "REPORTLOG",
                f"Query generation summary saved: {report_dir / 'query_generation_summary.json'}",
            )
        except Exception as e:
            _log_user("REPORTLOG", f"Failed to write query generation summary: {e}")

        _log_user("PIPELINE", "Starting DeepSeek sections 1-5")
        section_texts, intermediate_md = self.llm_client.run_sections(
            qwen_text=qwen_text,
            presentation_dir=presentation_dir,
            tavily_queries_by_category=tavily_queries_by_category,
            stats=stats
        )

        _log_user("PIPELINE", "Starting final verdict (section 6)")
        final_text = self.llm_client.run_final_verdict(
            intermediate_md=intermediate_md,
            presentation_dir=presentation_dir,
            stats=stats
        )

        # Сборка markdown через интерфейс форматирования
        full_md = self.markdown_builder.build_full_markdown(section_texts=section_texts, final_text=final_text)
        md_path.write_text(full_md, encoding="utf-8")
        _log_user("REPORT", f"Markdown saved to: {md_path} ({len(full_md)} chars)")

        _log_user("REPORT", f"Converting MD to DOCX: {md_path} -> {docx_path}")
        # Конвертация MD → DOCX через интерфейс
        self.docx_converter.convert_md_to_docx(md_path=md_path, docx_path=docx_path)
        docx_size = docx_path.stat().st_size if docx_path.exists() else 0
        _log_user("REPORT", f"DOCX saved to: {docx_path} ({docx_size} bytes)")
        _log_user("REPORT", f"Pipeline completed: report ready at {docx_path}")

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
            self.logger.log("REPORTLOG", f"Unified report log saved: {report_log_path}")
        except Exception as e:
            self.logger.log("REPORTLOG", f"Failed to write unified report log: {e}")

        return docx_path, stats

    async def run_full_pipeline(
        self,
        pdf_path: Path,
        presentation_dir: str,
        user_label: Optional[str] = None,
        telegram_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Tuple[Path, Dict[str, int]]:
        """
        Запуск полного пайплайна: PDF -> отчёт DOCX + статистика.
        Параллельно фиксируем отчёт и пользователя в БД.
        """
        # Пайплайн выполняем синхронно в отдельном потоке, чтобы не блокировать event loop.
        docx_path, stats = await anyio.to_thread.run_sync(
            self._run_full_pipeline_sync,
            pdf_path,
            presentation_dir,
            user_label,
        )

        user_id_db: Optional[int] = None
        if telegram_id is not None:
            user = await self.user_repo.get_or_create(telegram_id=telegram_id, username=username)
            user_id_db = user.id

        # Пути к логам можно восстановить по presentation_dir
        report_log_path = str(REPORT_LOG_ROOT / presentation_dir / "report_log.json")
        await self.report_repo.create_report(
            presentation_dir=presentation_dir,
            user_id=user_id_db,
            pdf_path=str(pdf_path),
            docx_path=str(docx_path),
            report_log_path=report_log_path,
        )

        return docx_path, stats


def get_pipeline_service(db: AsyncSession) -> PipelineService:
    """
    Фабрика для использования с FastAPI Depends (инъекция зависимостей).
    """
    return PipelineService(db=db)

