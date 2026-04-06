from __future__ import annotations

from pathlib import Path
from typing import List

import os
import fitz  # PyMuPDF

from .interfaces import ISlidesExtractor


class PdfSlidesExtractor(ISlidesExtractor):
    """
    Реализация ISlidesExtractor: полноценный перенос логики из pdf_to_images.py.
    """

    def pdf_to_images(
        self,
        pdf_path: Path,
        output_dir: Path,
        dpi: int = 150,
        image_format: str = "png",
    ) -> List[str]:
        if not pdf_path.exists():
            raise FileNotFoundError(f"Файл не найден: {pdf_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        pdf_document = fitz.open(str(pdf_path))
        image_paths: List[str] = []

        try:
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)

                output_filename = f"page_{page_num + 1:03d}.{image_format.lower()}"
                output_path = output_dir / output_filename

                pix.save(str(output_path))
                image_paths.append(str(output_path))
        finally:
            pdf_document.close()

        return image_paths

