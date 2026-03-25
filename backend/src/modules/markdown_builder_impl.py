from __future__ import annotations

from pathlib import Path
from typing import List

from .interfaces import IMarkdownBuilder


class MarkdownBuilderService(IMarkdownBuilder):
    """
    Реализация IMarkdownBuilder: сборка финального markdown‑отчёта.
    """

    def build_full_markdown(self, section_texts: List[str], final_text: str) -> str:
        """
        Сборка финального markdown из разделов 1-5 и итогового вердикта.
        """
        intermediate_md = "\n\n\n".join(s.strip() for s in section_texts)
        full_md = intermediate_md + "\n\n\n" + final_text.strip() + "\n"
        return full_md

