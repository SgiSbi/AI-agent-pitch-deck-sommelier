from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable, Any, List, Tuple, Dict, Optional


@runtime_checkable
class ILogger(Protocol):
    """
    Интерфейс логирования событий пайплайна и сервисов.
    """

    def log(self, component: str, message: str) -> None:
        ...


@runtime_checkable
class IBotGateway(Protocol):
    """
    Интерфейс взаимодействия с ботом / внешним клиентом:
    - приём PDF и данных пользователя;
    - возврат пути к сохранённому файлу и идентификатору презентации.
    """

    def save_uploaded_pdf(self, filename: str, content: bytes) -> Tuple[Path, str]:
        ...


@runtime_checkable
class ISlidesExtractor(Protocol):
    """
    Интерфейс получения изображений из PDF.
    """

    def pdf_to_images(self, pdf_path: Path, output_dir: Path) -> List[str]:
        ...


@runtime_checkable
class ILLMClient(Protocol):
    """
    Централизованный интерфейс для всех взаимодействий с LLM.
    Все HTTP вызовы к LLM API должны происходить только через реализацию этого интерфейса.
    """

    def extract_information_from_images(
        self, 
        image_paths: List[str], 
        presentation_dir: str
    ) -> str:
        """Этап 2: Извлечение информации из слайдов через Qwen (vision)."""
        ...
    
    def generate_tavily_queries(
        self, 
        qwen_text: str, 
        presentation_dir: str,
        stats: Optional[Dict[str, int]] = None
    ) -> Dict[str, List[str]]:
        """Генерация поисковых запросов для Tavily по категориям."""
        ...
    
    def run_section(
        self,
        prompt_filename: str,
        qwen_text: str,
        presentation_dir: str,
        search_results: Optional[str] = None,
        stats: Optional[Dict[str, int]] = None
    ) -> str:
        """Этап 3: Отправка одной секции в DeepSeek с учетом результатов поиска."""
        ...
    
    def run_sections(
        self, 
        qwen_text: str,
        presentation_dir: str,
        tavily_queries_by_category: Optional[Dict[str, List[str]]] = None,
        stats: Optional[Dict[str, int]] = None
    ) -> Tuple[List[str], str]:
        """Этап 3: Параллельный запуск секций 1-5 в DeepSeek."""
        ...
    
    def run_final_verdict(
        self, 
        intermediate_md: str, 
        presentation_dir: str,
        stats: Optional[Dict[str, int]] = None
    ) -> str:
        """Этап 4: Финальный вердикт (секция 6) в DeepSeek."""
        ...


@runtime_checkable
class ISearchClient(Protocol):
    """
    Интерфейс поисковой системы\.
    """

    def search(self, queries: List[str], max_results: int = 4) -> str:
        ...


@runtime_checkable
class IMarkdownBuilder(Protocol):
    """
    Интерфейс сборки финального markdown‑отчёта.
    """

    def build_full_markdown(self, section_texts: List[str], final_text: str) -> str:
        ...


@runtime_checkable
class IDocxConverter(Protocol):
    """
    Интерфейс конвертации markdown → DOCX.
    """

    def convert_md_to_docx(self, md_path: Path, docx_path: Path) -> None:
        ...


@runtime_checkable
class IWordFormatter(Protocol):
    """
    Интерфейс форматирования содержимого Word‑документа.
    (На текущем этапе логика скрыта внутри markdown → DOCX конвертера.)
    """

    def format_document(self, docx_path: Path) -> None:
        ...
