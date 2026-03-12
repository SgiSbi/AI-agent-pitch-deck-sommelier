from pathlib import Path
from typing import Tuple

from fastapi import UploadFile, HTTPException
from pydantic import BaseModel

from .paths import TMP_DIR, RAW_PRESENTATIONS_ROOT


def save_uploaded_pdf(file: UploadFile) -> Tuple[Path, str]:
    """
    Сохраняет загруженный PDF во временный файл и возвращает (pdf_path, presentation_dir).
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
    import uuid as _uuid

    date_str = datetime.now(timezone(timedelta(hours=7))).strftime("%Y%m%d")
    # Короткий UUID как идентификатор запуска
    run_id = _uuid.uuid4().hex[:8]
    presentation_dir = f"{safe_stem}_{date_str}_{run_id}"

    pdf_path = RAW_PRESENTATIONS_ROOT / f"{presentation_dir}.pdf"
    with pdf_path.open("wb") as f:
        f.write(file.file.read())

    return pdf_path, presentation_dir


class DeepSeekSectionRequest(BaseModel):
    prompt_filename: str
    qwen_text: str
    presentation_dir: str

