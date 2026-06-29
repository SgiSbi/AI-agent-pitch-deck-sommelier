from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..db.session import get_db, AsyncSessionLocal
from ..modules.deps import get_current_user, require_pipeline_access, save_uploaded_pdf
from ..modules.paths import REPORT_LOG_ROOT
from ..repositories.sqlalchemy_repos import SqlAlchemyReportRepository
from ..schemas.pipeline import SectionName
from ..services.pipeline_service import get_pipeline_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


async def _run_report_in_background(
    report_id: int,
    pdf_path: str,
    presentation_dir: str,
    user_login: str,
    user_id: int,
) -> None:
    async with AsyncSessionLocal() as db:
        report_repo = SqlAlchemyReportRepository(db)
        service = get_pipeline_service(db=db)
        try:
            docx_path, stats = await service.run_full_pipeline_only(
                pdf_path=Path(pdf_path),
                presentation_dir=presentation_dir,
                user_label=user_login,
            )
            report_log_path = str(REPORT_LOG_ROOT / presentation_dir / "report_log.json")
            await report_repo.mark_completed(
                report_id=report_id,
                docx_path=str(docx_path),
                report_log_path=report_log_path,
                input_tokens=stats.get("input_tokens", 0),
                output_tokens=stats.get("output_tokens", 0),
                tavily_requests=stats.get("tavily_requests", 0),
            )
        except Exception as e:
            await report_repo.mark_failed(report_id=report_id, error_message=str(e))


async def _run_section_report_in_background(
    report_id: int,
    pdf_path: str,
    presentation_dir: str,
    section: str,
    user_login: str,
    user_id: int,
) -> None:
    async with AsyncSessionLocal() as db:
        report_repo = SqlAlchemyReportRepository(db)
        service = get_pipeline_service(db=db)
        try:
            docx_path, stats = await service.run_single_section_only(
                pdf_path=Path(pdf_path),
                presentation_dir=presentation_dir,
                section=section,
                user_label=user_login,
            )
            report_log_path = str(REPORT_LOG_ROOT / presentation_dir / "report_log.json")
            await report_repo.mark_completed(
                report_id=report_id,
                docx_path=str(docx_path),
                report_log_path=report_log_path,
                input_tokens=stats.get("input_tokens", 0),
                output_tokens=stats.get("output_tokens", 0),
                tavily_requests=stats.get("tavily_requests", 0),
            )
        except Exception as e:
            await report_repo.mark_failed(report_id=report_id, error_message=str(e))


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


@router.post("/process-pdf/async")
async def process_pdf_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pipeline_access),
) -> dict:
    """Принимает PDF и ставит генерацию отчета в фоновую очередь."""
    pdf_path, presentation_dir = save_uploaded_pdf(file)
    report_repo = SqlAlchemyReportRepository(db)
    report = await report_repo.create_report(
        presentation_dir=presentation_dir,
        user_id=current_user.id,
        pdf_path=str(pdf_path),
        docx_path=None,
        report_log_path=None,
        status="processing",
        error_message=None,
    )
    background_tasks.add_task(
        _run_report_in_background,
        report.id,
        str(pdf_path),
        presentation_dir,
        current_user.login,
        current_user.id,
    )
    return {
        "report_id": report.id,
        "status": report.status,
        "detail": "Отчет принят в обработку и будет доступен после окончания генерации",
    }


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


@router.post("/process-pdf/section/async")
async def process_pdf_section_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    section: SectionName = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pipeline_access),
) -> dict:
    """Ставит генерацию одной секции отчёта в фоновую очередь."""
    pdf_path, presentation_dir = save_uploaded_pdf(file)
    report_repo = SqlAlchemyReportRepository(db)
    report = await report_repo.create_report(
        presentation_dir=f"{presentation_dir}_{section.value}",
        user_id=current_user.id,
        pdf_path=str(pdf_path),
        docx_path=None,
        report_log_path=None,
        status="processing",
        error_message=None,
    )
    background_tasks.add_task(
        _run_section_report_in_background,
        report.id,
        str(pdf_path),
        presentation_dir,
        section.value,
        current_user.login,
        current_user.id,
    )
    return {
        "report_id": report.id,
        "status": report.status,
        "detail": f"Секция '{section.value}' принята в обработку",
    }


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Скачать DOCX отчёт по id (только свой отчёт)."""
    service = get_pipeline_service(db=db)
    docx_path = await service.get_report_docx(
        report_id=report_id,
        current_user_id=current_user.id,
        current_user_role=current_user.role,
    )
    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=docx_path.name,
    )


@router.get("/reports/{report_id}/status")
async def report_status(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    repo = SqlAlchemyReportRepository(db)
    report = await repo.get_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Нет доступа к этому отчёту")
    return {
        "id": report.id,
        "status": report.status,
        "error_message": report.error_message,
        "docx_available": bool(report.docx_path),
    }
