#!/usr/bin/env python3
"""
Скрипт для конвертации Markdown (.md) в DOCX с сохранением форматирования,
включая многоуровневые списки и таблицы.

Использует pandoc через библиотеку pypandoc.
Требуется установка pandoc (https://pandoc.org/installing.html) и pypandoc (pip install pypandoc).
"""

import sys
import subprocess
import pypandoc

def check_pandoc() -> bool:
    """Проверяет, доступен ли pandoc в системе."""
    try:
        subprocess.run(['pandoc', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def convert_md_to_docx(input_file: str, output_file: str) -> None:
    """
    Конвертирует Markdown файл в DOCX с помощью pypandoc.
    
    Args:
        input_file: путь к входному .md файлу
        output_file: путь для сохранения .docx файла
    
    Raises:
        Exception: при ошибке конвертации
    """
    # pandoc автоматически обрабатывает таблицы, вложенные списки и прочее
    pypandoc.convert_file(input_file, 'docx', outputfile=output_file)

def main():
    if len(sys.argv) < 3:
        print("Использование: python md_to_docx.py <входной_файл.md> <выходной_файл.docx>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if not check_pandoc():
        print("Ошибка: pandoc не найден. Установите pandoc с https://pandoc.org/installing.html")
        sys.exit(1)

    try:
        convert_md_to_docx(input_file, output_file)
        print(f"Готово: {input_file} -> {output_file}")
    except Exception as e:
        print(f"Ошибка конвертации: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()