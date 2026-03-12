"""
Интерфейсы (Protocol) для слоя репозиториев.

Здесь описываются контракты взаимодействия с хранилищами данных (БД и т.п.).
Конкретные реализации могут работать с Postgres, файлами, Redis и т.д.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Dict, Any, Optional


@runtime_checkable
class UserStatsRepository(Protocol):
    """
    Репозиторий для хранения статистики использования пайплайна пользователями.

    Возможные реализации:
    - БД (Postgres, SQLite и т.п.)
    - внешнее хранилище метрик
    - файловое хранилище
    """

    def add_run_stats(self, username: Optional[str], stats: Dict[str, int]) -> None:
        """
        Сохранить агрегированную статистику одного запуска пайплайна.

        :param username: Telegram username пользователя (или None, если неизвестен).
        :param stats: Словарь с ключами вроде "input_tokens", "output_tokens",
                      "tavily_requests" и их значениями.
        """
        ...


@runtime_checkable
class PresentationReportRepository(Protocol):
    """
    Репозиторий для хранения артефактов отчёта (PDF, MD, DOCX и служебные JSON).
    Сейчас пайплайн пишет их в файловую систему; этот интерфейс нужен для
    будущего переноса в БД или объектное хранилище.
    """

    def save_paths_summary(self, presentation_dir: str, summary: Dict[str, Any]) -> None:
        """
        Сохранить сводную информацию по отчёту (пути к файлам, размеры и т.п.).
        """
        ...


@runtime_checkable
class UserRepository(Protocol):
    """
    Репозиторий пользователей.
    """

    def get_or_create(self, telegram_id: int, username: Optional[str]) -> Any:
        """
        Найти пользователя по telegram_id или создать нового.
        """
        ...


@runtime_checkable
class ReportRepository(Protocol):
    """
    Репозиторий отчётов.
    """

    def create_report(
        self,
        presentation_dir: str,
        user_id: Optional[int],
        pdf_path: Optional[str],
        docx_path: Optional[str],
        report_log_path: Optional[str],
    ) -> Any:
        """
        Создать запись об отчёте.
        """
        ...