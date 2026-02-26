import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .pipeline import (
    run_full_pipeline,
    TMP_DIR,
    extract_slides_stage,
    qwen_from_slides_stage,
    run_deepseek_sections,
    run_final_verdict,
    build_full_markdown,
)
from .qwen_image import analyze_image_with_qwen


app = FastAPI(title="Pitch Deck Analyzer API")


def _save_uploaded_pdf(file: UploadFile) -> Path:
    """
    Сохраняет загруженный PDF во временный файл и возвращает путь.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Ожидается PDF файл.")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    filename = file.filename or f"input_{run_id}.pdf"
    pdf_path = TMP_DIR / f"{run_id}_{filename}"

    with pdf_path.open("wb") as f:
        f.write(file.file.read())

    return pdf_path


class DeepSeekSectionRequest(BaseModel):
    prompt_filename: str
    qwen_text: str
    presentation_dir: str


@app.post("/process-pdf")
def process_pdf(file: UploadFile = File(...)) -> FileResponse:
    """
    Полный пайплайн: принимает PDF-файл и возвращает DOCX.
    """
    pdf_path = _save_uploaded_pdf(file)
    docx_path: Path = run_full_pipeline(pdf_path)

    if not docx_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать DOCX.")

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=docx_path.name,
    )


@app.post("/stage/extract-slides")
def stage_extract_slides(file: UploadFile = File(...)) -> JSONResponse:
    """
    Этап 1: только извлечение слайдов из PDF.
    """
    pdf_path = _save_uploaded_pdf(file)
    run_id = uuid.uuid4().hex
    presentation_dir = f"{pdf_path.stem}_{run_id}"
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)
    return JSONResponse(
        {
            "presentation_dir": presentation_dir,
            "images": image_paths,
        }
    )


@app.post("/stage/qwen-from-pdf")
def stage_qwen_from_pdf(file: UploadFile = File(...)) -> JSONResponse:
    """
    Этап 1 + 2: PDF -> слайды -> Qwen.
    """
    pdf_path = _save_uploaded_pdf(file)
    run_id = uuid.uuid4().hex
    presentation_dir = f"{pdf_path.stem}_{run_id}"
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)
    qwen_text = qwen_from_slides_stage(image_paths=image_paths, presentation_dir=presentation_dir)
    return JSONResponse(
        {
            "presentation_dir": presentation_dir,
            "images": image_paths,
            "qwen_text": qwen_text,
        }
    )


@app.post("/stage/deepseek-section")
def stage_deepseek_section(body: DeepSeekSectionRequest) -> JSONResponse:
    """
    Этап 3: отправка отдельного модуля в DeepSeek.

    Ожидает на вход:
    - prompt_filename: имя файла промпта из директории promts (например, '1_info_from_pdf_prompt.md')
    - qwen_text: текст, извлечённый Qwen из слайдов
    - presentation_dir: идентификатор директории презентации (для логов и сохранения запросов/ответов)
    """
    # Используем только шаг DeepSeek, не трогая PDF.
    from .pipeline import send_section_to_deepseek

    section_text = send_section_to_deepseek(
        prompt_filename=body.prompt_filename,
        qwen_text=body.qwen_text,
        presentation_dir=body.presentation_dir,
    )

    return JSONResponse(
        {
            "presentation_dir": body.presentation_dir,
            "prompt_filename": body.prompt_filename,
            "section_text": section_text,
        }
    )


@app.post("/debug/pdf-to-images")
def debug_pdf_to_images(file: UploadFile = File(...)) -> JSONResponse:
    """
    DEBUG: только конвертация PDF в изображения.
    Возвращает список путей к слайдам.
    """
    pdf_path = _save_uploaded_pdf(file)
    run_id = uuid.uuid4().hex
    presentation_dir = f"{pdf_path.stem}_debug_{run_id}"
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)

    # Возвращаем относительные пути для удобства
    rel_paths = [str(Path(p).relative_to(Path.cwd())) for p in image_paths]
    return JSONResponse({"images": rel_paths})


@app.post("/debug/qwen-from-pdf")
def debug_qwen_from_pdf(file: UploadFile = File(...)) -> JSONResponse:
    """
    DEBUG: PDF -> изображения -> Qwen.
    Возвращает сырой текст, извлечённый Qwen.
    """
    pdf_path = _save_uploaded_pdf(file)
    run_id = uuid.uuid4().hex
    presentation_dir = f"{pdf_path.stem}_debug_{run_id}"
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)

    qwen_text = qwen_from_slides_stage(image_paths=image_paths, presentation_dir=presentation_dir)
    return JSONResponse(
        {
            "presentation_dir": presentation_dir,
            "qwen_text": qwen_text,
        }
    )


@app.post("/debug/markdown-from-pdf")
def debug_markdown_from_pdf(file: UploadFile = File(...)) -> JSONResponse:
    """
    DEBUG: PDF -> изображения -> Qwen -> DeepSeek (1–5) -> финальный вердикт.
    Возвращает полный markdown без генерации DOCX.
    """
    pdf_path = _save_uploaded_pdf(file)
    run_id = uuid.uuid4().hex
    presentation_dir = f"{pdf_path.stem}_debug_{run_id}"
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)

    qwen_text = qwen_from_slides_stage(image_paths=image_paths, presentation_dir=presentation_dir)
    section_texts, intermediate_md = run_deepseek_sections(
        qwen_text=qwen_text,
        presentation_dir=presentation_dir,
    )
    final_text = run_final_verdict(intermediate_md=intermediate_md)
    full_md = build_full_markdown(section_texts=section_texts, final_text=final_text)

    return JSONResponse(
        {
            "qwen_text": qwen_text,
            "section_texts": section_texts,
            "final_text": final_text,
            "markdown": full_md,
        }
    )


@app.post("/stage/qwen-image")
def stage_qwen_image(
    file: UploadFile = File(...),
    question: str | None = Query(default="Что изображено на этой картинке?", description="Вопрос для анализа изображения"),
) -> JSONResponse:
    """
    Отправка одного изображения в Qwen (vision) с текстовым вопросом.

    Принимает:
    - file: изображение (png/jpg) через multipart/form-data
    - question: опциональный query-параметр с вопросом (по умолчанию: "Что изображено на этой картинке?")
    """
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg"):
        raise HTTPException(status_code=400, detail="Ожидается PNG или JPEG изображение.")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    filename = file.filename or f"image_{run_id}.png"
    image_path = TMP_DIR / f"{run_id}_{filename}"

    with image_path.open("wb") as f:
        f.write(file.file.read())

    answer = analyze_image_with_qwen(image_path=image_path, question=question)

    return JSONResponse(
        {
            "question": question,
            "answer": answer,
            "image_path": str(image_path),
        }
    )

