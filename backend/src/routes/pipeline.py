from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..services.pipeline_service import get_pipeline_service
from ..modules.deps import save_uploaded_pdf


router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/process-pdf")
async def process_pdf(
    file: UploadFile = File(...),
    user_id: str | None = Form(default=None),
    username: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Полный пайплайн: принимает PDF-файл и возвращает DOCX."""
    
    pdf_path, presentation_dir = save_uploaded_pdf(file)
    
    user_label_parts: list[str] = []
    if username:
        user_label_parts.append(f"@{username}")
    if user_id:
        user_label_parts.append(f"id={user_id}")
    user_label = " ".join(user_label_parts) if user_label_parts else None
    
    # Получение сервиса через dependency injection
    service = get_pipeline_service(db=db)
    
    telegram_id_int = None
    try:
        if user_id is not None:
            telegram_id_int = int(user_id)
    except ValueError:
        telegram_id_int = None
    
    # Запуск пайплайна через сервис (который использует только интерфейсы)
    docx_path, stats = await service.run_full_pipeline(
        pdf_path,
        presentation_dir,
        user_label=user_label,
        telegram_id=telegram_id_int,
        username=username,
    )
    
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
