from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..modules.deps import save_uploaded_pdf
from ..modules.llm_client_impl import DefaultLLMClient
from ..modules.paths import TMP_DIR, SLIDES_ROOT
from ..services.pipeline_service import get_pipeline_service


router = APIRouter(prefix="/debug", tags=["debug"])


@router.post("/stage/extract-slides")
async def stage_extract_slides(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    """
    Этап 1: только извлечение слайдов из PDF.
    """
    pdf_path, presentation_dir = save_uploaded_pdf(file)
    slides_dir = SLIDES_ROOT / presentation_dir
    
    service = get_pipeline_service(db=db)
    image_paths = service.slides_extractor.pdf_to_images(pdf_path=pdf_path, output_dir=slides_dir)
    
    return JSONResponse(
        {
            "presentation_dir": presentation_dir,
            "images": image_paths,
        }
    )


@router.post("/markdown-from-pdf")
async def debug_markdown_from_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    DEBUG: PDF -> изображения -> Qwen -> DeepSeek (1–5) -> финальный вердикт.
    Возвращает полный markdown без генерации DOCX.
    """
    pdf_path, presentation_dir = save_uploaded_pdf(file)
    
    # Получение сервиса с инжектированными зависимостями
    service = get_pipeline_service(db=db)
    
    # Извлечение слайдов через интерфейс
    slides_dir = SLIDES_ROOT / presentation_dir
    slides_dir.mkdir(parents=True, exist_ok=True)
    image_paths = service.slides_extractor.pdf_to_images(pdf_path, slides_dir)
    
    # Все LLM операции через интерфейс ILLMClient
    qwen_text = service.llm_client.extract_information_from_images(
        image_paths=image_paths,
        presentation_dir=presentation_dir,
        stats=None
    )
    
    tavily_queries = service.llm_client.generate_tavily_queries(
        qwen_text=qwen_text,
        presentation_dir=presentation_dir
    )
    
    section_texts, intermediate_md = service.llm_client.run_sections(
        qwen_text=qwen_text,
        presentation_dir=presentation_dir,
        tavily_queries_by_category=tavily_queries
    )
    
    final_text = service.llm_client.run_final_verdict(
        intermediate_md=intermediate_md,
        presentation_dir=presentation_dir
    )
    
    full_md = service.markdown_builder.build_full_markdown(section_texts, final_text)
    
    return JSONResponse({
        "qwen_text": qwen_text,
        "section_texts": section_texts,
        "final_text": final_text,
        "markdown": full_md,
    })


@router.post("/stage/qwen-image")
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
    import uuid as _uuid

    run_id = _uuid.uuid4().hex
    filename = file.filename or f"image_{run_id}.png"
    image_path = TMP_DIR / f"{run_id}_{filename}"

    with image_path.open("wb") as f:
        f.write(file.file.read())

    client = DefaultLLMClient()
    answer = client.analyze_image(image_path=image_path, question=question or "")

    return JSONResponse(
        {
            "question": question,
            "answer": answer,
            "image_path": str(image_path),
        }
    )


@router.post("/db/add_new_user")
async def db_add_new_user(
    telegram_id: int,
    username: str,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Добавление нового пользователя в базу данных (отладочная ручка).
    Для боевого использования лучше использовать /users.
    """
    from ..db.models import User

    user = User(telegram_id=telegram_id, username=username)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return JSONResponse(
        {
            "message": "Пользователь добавлен в базу данных.",
            "id": user.id,
        }
    )
