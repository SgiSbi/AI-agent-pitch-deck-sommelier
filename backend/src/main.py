import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .pipeline import (
    run_full_pipeline,
    TMP_DIR,
    RAW_PRESENTATIONS_ROOT,
    extract_slides_stage,
    qwen_from_slides_stage,
    run_deepseek_sections,
    run_final_verdict,
    build_full_markdown,
)
from .qwen_image import analyze_image_with_qwen


app = FastAPI(title="Pitch Deck Analyzer API")


def _save_uploaded_pdf(file: UploadFile) -> tuple[Path, str]:
    """
    Сохраняет загруженный PDF во временный файл и возвращает путь + идентификатор презентации.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Ожидается PDF файл.")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PRESENTATIONS_ROOT.mkdir(parents=True, exist_ok=True)

    original_name = file.filename or "presentation.pdf"
    safe_stem = Path(original_name).stem.replace(" ", "_")
    if not safe_stem:
        safe_stem = "presentation"

    from datetime import datetime, timedelta, timezone

    date_str = datetime.now(timezone(timedelta(hours=7))).strftime("%Y%m%d")
    run_id = uuid.uuid4().hex[:8]
    presentation_dir = f"{safe_stem}_{date_str}_{run_id}"

    pdf_path = RAW_PRESENTATIONS_ROOT / f"{presentation_dir}.pdf"
    with pdf_path.open("wb") as f:
        f.write(file.file.read())

    return pdf_path, presentation_dir


class DeepSeekSectionRequest(BaseModel):
    prompt_filename: str
    qwen_text: str
    presentation_dir: str


@app.post("/process-pdf")
def process_pdf(
    file: UploadFile = File(...),
    user_id: str | None = Form(default=None),
    username: str | None = Form(default=None),
) -> FileResponse:
    """
    Полный пайплайн: принимает PDF-файл и возвращает DOCX.
    """
    pdf_path, presentation_dir = _save_uploaded_pdf(file)

    user_label_parts: list[str] = []
    if username:
        user_label_parts.append(f"@{username}")
    if user_id:
        user_label_parts.append(f"id={user_id}")
    user_label = " ".join(user_label_parts) if user_label_parts else None

    docx_path, stats = run_full_pipeline(pdf_path, presentation_dir, user_label=user_label)

    if not docx_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать DOCX.")

    response = FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=docx_path.name,
    )
    response.headers["X-Input-Tokens"] = str(stats.get("input_tokens", 0))
    response.headers["X-Output-Tokens"] = str(stats.get("output_tokens", 0))
    response.headers["X-Tavily-Requests"] = str(stats.get("tavily_requests", 0))
    return response


@app.post("/stage/extract-slides")
def stage_extract_slides(file: UploadFile = File(...)) -> JSONResponse:
    """
    Этап 1: только извлечение слайдов из PDF.
    """
    pdf_path, presentation_dir = _save_uploaded_pdf(file)
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
    pdf_path, presentation_dir = _save_uploaded_pdf(file)
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
    """
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


@app.post("/debug/markdown-from-pdf")
def debug_markdown_from_pdf(file: UploadFile = File(...)) -> JSONResponse:
    """
    DEBUG: PDF -> изображения -> Qwen -> DeepSeek (1–5) -> финальный вердикт.
    Возвращает полный markdown без генерации DOCX.
    """
    pdf_path, presentation_dir = _save_uploaded_pdf(file)
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)

    qwen_text = qwen_from_slides_stage(image_paths=image_paths, presentation_dir=presentation_dir)
    section_texts, intermediate_md = run_deepseek_sections(
        qwen_text=qwen_text,
        presentation_dir=presentation_dir,
    )
    final_text = run_final_verdict(intermediate_md=intermediate_md, presentation_dir=presentation_dir)
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
    question: str | None = Query(
        default="Что изображено на этой картинке?",
        description="Вопрос для анализа изображения",
    ),
) -> JSONResponse:
    """
    Отправка одного изображения в Qwen (vision) с текстовым вопросом.
    """
    if file.content_type not in ("image/png", "image/jpeg", "image/jpg"):
        raise HTTPException(status_code=400, detail="Ожидается PNG или JPEG изображение.")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    filename = file.filename or f"image_{run_id}.png"
    image_path = TMP_DIR / f"{run_id}_{filename}"

    with image_path.open("wb") as f:
        f.write(file.file.read())

    answer = analyze_image_with_qwen(image_path=image_path, question=question or "")

    return JSONResponse(
        {
            "question": question,
            "answer": answer,
            "image_path": str(image_path),
        }
    )



def _get_directory_size(path: Path) -> int:
    """
    Рекурсивно вычисляет размер директории в байтах.
    """
    total_size = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total_size


def _format_size(size_bytes: int) -> str:
    """
    Форматирует размер в человекочитаемый формат.
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


@app.get("/tmp/size")
def get_tmp_size() -> JSONResponse:
    """
    Возвращает текущий размер директории /backend/tmp/*.
    """
    if not TMP_DIR.exists():
        return JSONResponse(
            {
                "size_bytes": 0,
                "size_formatted": "0 B",
                "files_count": 0,
                "message": "Директория tmp не существует",
            }
        )

    size_bytes = _get_directory_size(TMP_DIR)
    files_count = sum(1 for _ in TMP_DIR.rglob("*") if _.is_file())

    return JSONResponse(
        {
            "size_bytes": size_bytes,
            "size_formatted": _format_size(size_bytes),
            "files_count": files_count,
            "path": str(TMP_DIR),
        }
    )


@app.delete("/tmp/cleanup")
def cleanup_tmp_directory() -> JSONResponse:
    """
    Очищает директорию /backend/tmp/*, удаляя все файлы и поддиректории.
    Сохраняет только .gitkeep файл, если он существует.
    """
    if not TMP_DIR.exists():
        return JSONResponse(
            {
                "success": True,
                "message": "Директория tmp не существует",
                "deleted_files": 0,
                "freed_bytes": 0,
                "freed_formatted": "0 B",
            }
        )

    # Получаем размер до очистки
    size_before = _get_directory_size(TMP_DIR)
    files_count = 0

    import shutil

    try:
        # Удаляем все содержимое, кроме .gitkeep
        for item in TMP_DIR.iterdir():
            if item.name == ".gitkeep":
                continue

            try:
                if item.is_file():
                    item.unlink()
                    files_count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    files_count += 1
            except (OSError, PermissionError) as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Ошибка при удалении {item.name}: {str(e)}",
                )

        size_after = _get_directory_size(TMP_DIR)
        freed_bytes = size_before - size_after

        return JSONResponse(
            {
                "success": True,
                "message": "Директория tmp успешно очищена",
                "deleted_items": files_count,
                "freed_bytes": freed_bytes,
                "freed_formatted": _format_size(freed_bytes),
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при очистке директории: {str(e)}",
        )

