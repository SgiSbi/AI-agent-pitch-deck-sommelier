from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .interfaces import ILogger


class ConsoleLogger(ILogger):
    """
    Реализация ILogger, логирующая сообщения в stdout.
    Формат: [ДД-ММ-ГГГГ ЧЧ:ММ:СС] [COMPONENT] message (GMT+7).
    Если передан user_label, добавляет [user=<label>] перед сообщением.
    """

    def __init__(self, tz_offset_hours: int = 7) -> None:
        self._tz = timezone(timedelta(hours=tz_offset_hours))

    def _ts(self) -> str:
        return datetime.now(self._tz).strftime("%d-%m-%Y %H:%M:%S")

    def log(self, component: str, message: str, user_label: Optional[str] = None) -> None:
        prefix = f"[user={user_label}] " if user_label else ""
        print(f"[{self._ts()}] [{component}] {prefix}{message}")


# Глобальный экземпляр логгера по умолчанию для использования в пайплайне.
default_logger: ILogger = ConsoleLogger()

