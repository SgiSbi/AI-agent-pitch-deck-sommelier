import os
from pathlib import Path

import fitz  # PyMuPDF


def pdf_to_images(
    pdf_path: str,
    output_folder: str = "output_images",
    dpi: int = 150,
    image_format: str = "png",
) -> list[str]:
    """
    Конвертирует PDF в изображения страниц.

    Args:
        pdf_path: Путь к PDF-файлу.
        output_folder: Директория для сохранения изображений.
        dpi: Разрешение (по умолчанию 150).
        image_format: Формат изображения ('png', 'jpg', 'jpeg').

    Returns:
        Список путей к созданным изображениям.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Файл не найден: {pdf_path}")

    Path(output_folder).mkdir(parents=True, exist_ok=True)

    pdf_document = fitz.open(pdf_path)
    image_paths: list[str] = []

    try:
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            output_filename = f"page_{page_num + 1:03d}.{image_format.lower()}"
            output_path = os.path.join(output_folder, output_filename)

            pix.save(output_path)
            image_paths.append(output_path)
    finally:
        pdf_document.close()

    return image_paths

