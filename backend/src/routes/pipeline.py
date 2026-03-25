from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..db.session import get_db
from ..modules.deps import get_current_user, require_pipeline_access, save_uploaded_pdf
from ..schemas.pipeline import SectionName
from ..services.pipeline_service import get_pipeline_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/process-pdf")
async def process_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pipeline_access),
) -> FileResponse:
    """Полный пайплайн: принимает PDF-файл и возвращает DOCX"""

    pdf_path, presentation_dir = save_uploaded_pdf(file)
    service = get_pipeline_service(db=db)

    docx_path, stats = await service.run_full_pipeline(
        pdf_path,
        presentation_dir,
        user_label=current_user.login,
        user_id=current_user.id,
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


@router.post("/process-pdf/section")
async def process_pdf_section(
    file: UploadFile = File(...),
    section: SectionName = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pipeline_access),
) -> FileResponse:
    """Генерация одной секции отчёта из PDF"""

    pdf_path, presentation_dir = save_uploaded_pdf(file)
    service = get_pipeline_service(db=db)

    docx_path, stats = await service.run_single_section(
        pdf_path,
        presentation_dir,
        section=section.value,
        user_label=current_user.login,
        user_id=current_user.id,
    )

    if not docx_path.exists():
        raise HTTPException(status_code=500, detail="Не удалось сгенерировать DOCX.")

    response = FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=docx_path.name,
    )
    response.headers["X-Section"] = section.value
    response.headers["X-Input-Tokens"] = str(stats.get("input_tokens", 0))
    response.headers["X-Output-Tokens"] = str(stats.get("output_tokens", 0))
    response.headers["X-Tavily-Requests"] = str(stats.get("tavily_requests", 0))
    return response
