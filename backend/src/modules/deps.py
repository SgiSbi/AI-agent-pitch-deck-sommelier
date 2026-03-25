from __future__ import annotations

from pathlib import Path
from typing import Tuple

from fastapi import Depends, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .paths import TMP_DIR, RAW_PRESENTATIONS_ROOT
from .security import decode_access_token
from ..db.session import get_db
from ..db.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login/form")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учётные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        login = decode_access_token(token)
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.login == login))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Аккаунт заблокирован")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return current_user


async def require_pipeline_access(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role == "admin" or current_user.is_whitelisted:
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Доступ к пайплайну разрешён только администраторам и пользователям из вайтлиста",
    )


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
