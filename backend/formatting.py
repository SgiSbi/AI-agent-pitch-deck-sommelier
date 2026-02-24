#!/usr/bin/env python3
"""
Консольное приложение для пакетной конвертации Markdown в форматированный DOCX.

Логика:
1. Сканирует директорию ./tmp на наличие файлов .md
2. Конвертирует каждый файл в .docx (через pandoc)
3. Применяет форматирование (шрифт, размеры, отступы)
4. Сохраняет результат в директорию ./result с тем же именем файла

Требования:
- Установленный pandoc (системная утилита)
- Python библиотеки: pypandoc, python-docx
"""

import sys
import subprocess
from pathlib import Path

# Проверка и импорт сторонних библиотек
try:
    import pypandoc
except ImportError:
    print("Ошибка: Библиотека 'pypandoc' не найдена. Установите: pip install pypandoc")
    sys.exit(1)

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.oxml.ns import qn
except ImportError:
    print("Ошибка: Библиотека 'python-docx' не найдена. Установите: pip install python-docx")
    sys.exit(1)

# --- КОНФИГУРАЦИЯ ---
# Используем относительные пути относительно текущей рабочей директории
SOURCE_DIR = Path('tmp')
DEST_DIR = Path('result')

HEADING_STYLES = {
    'Heading 1': 20,
    'Заголовок 1': 20,
    'Heading 2': 16,
    'Заголовок 2': 16,
    'Heading 3': 14,
    'Заголовок 3': 14,
}
DEFAULT_FONT_SIZE = Pt(14)
FONT_NAME = 'Times New Roman'
# ---------------------

def check_pandoc() -> bool:
    """Проверяет, доступен ли pandoc в системе."""
    try:
        subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def set_font(run, font_name):
    """
    Надежно устанавливает шрифт для запуска (run), 
    включая настройки для латиницы и восточноазиатских символов.
    """
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run._element.rPr.rFonts.set(qn('w:ascii'), font_name)
    run._element.rPr.rFonts.set(qn('w:hAnsi'), font_name)
    run._element.rPr.rFonts.set(qn('w:cs'), font_name)

def format_paragraph(paragraph, heading_styles):
    """
    Применяет форматирование к абзацу.
    """
    # 1. Выравнивание по ширине
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # 2. Межстрочный интервал 1.5
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    paragraph.paragraph_format.line_spacing = 1.5
    
    style_name = paragraph.style.name

    for run in paragraph.runs:
        # 3. Шрифт Times New Roman
        set_font(run, FONT_NAME)

        # 4. Сначала устанавливаем всем текст 14 кегль
        run.font.size = DEFAULT_FONT_SIZE

        # 5. Затем переопределяем размер для заголовков
        if style_name in heading_styles:
            run.font.size = Pt(heading_styles[style_name])

def format_docx_file(input_path, output_path):
    """
    Открывает DOCX, применяет стили и сохраняет.
    """
    doc = Document(input_path)

    # 1. Форматируем основные абзацы документа
    for paragraph in doc.paragraphs:
        format_paragraph(paragraph, HEADING_STYLES)

    # 2. Форматируем абзацы внутри всех таблиц
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    format_paragraph(paragraph, HEADING_STYLES)

    doc.save(output_path)

def convert_md_to_docx(input_file: Path, output_file: Path) -> None:
    """
    Конвертирует Markdown файл в DOCX с помощью pypandoc.
    """
    pypandoc.convert_file(str(input_file), 'docx', outputfile=str(output_file))

def process_files():
    """Основная логика сканирования и обработки."""
    
    # 1. Проверка зависимостей
    if not check_pandoc():
        print("Критическая ошибка: pandoc не найден в системе.")
        print("Установите pandoc: https://pandoc.org/installing.html")
        sys.exit(1)

    # 2. Подготовка директорий
    if not SOURCE_DIR.exists():
        print(f"Ошибка: Исходная директория '{SOURCE_DIR}' не существует.")
        print("Создайте папку 'tmp' и положите туда .md файлы.")
        sys.exit(1)
    
    try:
        DEST_DIR.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print(f"Ошибка: Нет прав на создание директории '{DEST_DIR}'.")
        sys.exit(1)

    # 3. Поиск файлов
    md_files = list(SOURCE_DIR.glob('*.md'))
    
    if not md_files:
        print(f"В директории '{SOURCE_DIR}' не найдено файлов .md")
        sys.exit(0)

    print(f"Найдено файлов: {len(md_files)}")
    print(f"Начинаем обработку...\n")

    success_count = 0
    fail_count = 0

    for md_path in md_files:
        # Сохраняем с тем же именем, но с расширением .docx
        docx_path = DEST_DIR / f"{md_path.stem}.docx"
        
        print(f"Обработка: {md_path.name}...", end=" ")
        
        try:
            # Шаг 1: Конвертация
            convert_md_to_docx(md_path, docx_path)
            
            # Шаг 2: Форматирование (в тот же файл)
            format_docx_file(docx_path, docx_path)
            
            print("OK")
            success_count += 1
            
        except Exception as e:
            print(f"FAILED ({e})")
            fail_count += 1
            # Очищаем битый файл, если он создался
            if docx_path.exists():
                try:
                    docx_path.unlink()
                except:
                    pass

    print("\n" + "="*30)
    print(f"Готово. Успешно: {success_count}, Ошибок: {fail_count}")
    print(f"Результаты сохранены в: {DEST_DIR.resolve()}")

if __name__ == "__main__":
    process_files()