"""
Утилиты для инициализации и сброса БД.

Запускать вручную из консоли:

    python -m db.init_db           # создать/обновить таблицы
    python -m db.init_db --reset   # ПОЛНЫЙ сброс (drop_all + create_all)
"""

from __future__ import annotations

import argparse
import asyncio

from .session import Base, async_engine
from . import models  # noqa: F401 — важно для регистрации моделей в Base.metadata


async def _async_create_or_update_schema(reset: bool = False) -> None:
    """
    Асинхронное создание/сброс схемы БД поверх async_engine.
    """
    async with async_engine.begin() as conn:
        if reset:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def create_or_update_schema() -> None:
    """
    Создаёт недостающие таблицы в БД на основе ORM‑моделей.
    Существующие таблицы не трогает.
    """
    asyncio.run(_async_create_or_update_schema(reset=False))


def reset_db() -> None:
    """
    ПОЛНЫЙ сброс схемы: удаление всех таблиц и повторное создание.
    Использовать осторожно (желательно только в dev/stage окружении).
    """
    asyncio.run(_async_create_or_update_schema(reset=True))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DB init/reset helpers")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables before creating them again",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.reset:
        reset_db()
        print("Database schema has been reset (drop_all + create_all).")
    else:
        create_or_update_schema()
        print("Database schema has been created/updated.")


if __name__ == "__main__":
    main()

