import os
import fitz  # PyMuPDF
from pathlib import Path

def pdf_to_images(pdf_path, output_folder="output_images", dpi=150, image_format="png"):
    """
    Конвертирует PDF в изображения страниц.
    
    Args:
        pdf_path (str): Путь к PDF файлу
        output_folder (str): Папка для сохранения изображений
        dpi (int): Разрешение изображения (по умолчанию 150)
        image_format (str): Формат изображения ('png', 'jpg', 'jpeg')
    
    Returns:
        List[str]: Список путей к созданным изображениям
    """
    # Проверка существования файла
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Файл не найден: {pdf_path}")
    
    # Создание выходной папки
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    # Открытие PDF
    pdf_document = fitz.open(pdf_path)
    image_paths = []
    
    try:
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            
            # Матрица масштабирования для заданного DPI (72 DPI — базовое разрешение PDF)
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            # Рендеринг страницы в пиксельную карту
            pix = page.get_pixmap(matrix=mat)
            
            # Формирование имени файла
            output_filename = f"page_{page_num + 1:03d}.{image_format.lower()}"
            output_path = os.path.join(output_folder, output_filename)
            
            # Сохранение изображения
            pix.save(output_path)
            image_paths.append(output_path)
            print(f"Сохранена страница {page_num + 1} -> {output_path}")
    
    finally:
        pdf_document.close()
    
    print(f"\n✅ Успешно обработано {len(image_paths)} страниц")
    return image_paths


# Пример использования
if __name__ == "__main__":
    pdf_file = "tmp/input.pdf"  # Замените на путь к вашему PDF
    images = pdf_to_images(
        pdf_path=pdf_file,
        output_folder="tmp/slides",
        dpi=30,
        image_format="png"
    )