import asyncio
import os
import tempfile
from io import BytesIO

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from dotenv import load_dotenv
from pathlib import Path

# загрузить frontend/.env
load_dotenv(Path(__file__).resolve().parent / ".env.frontend")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/process-pdf")


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")


bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Отправь мне PDF-файл с презентацией, "
        "и я верну тебе инвестиционный отчёт в формате DOCX."
    )


@dp.message(F.document.mime_type == "application/pdf")
async def handle_pdf(message: Message) -> None:
    document = message.document
    file = await bot.get_file(document.file_id)
    file_path = file.file_path

    # Скачиваем PDF в память
    file_bytes = BytesIO()
    await bot.download_file(file_path, destination=file_bytes)
    file_bytes.seek(0)

    await message.answer("Обрабатываю презентацию, это может занять несколько минут...")

    # Отправляем PDF в backend
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field(
            "file",
            file_bytes,
            filename=document.file_name or "presentation.pdf",
            content_type="application/pdf",
        )

        async with session.post(BACKEND_URL, data=data) as resp:
            if resp.status != 200:
                text = await resp.text()
                await message.answer(f"Ошибка при обработке на сервере: {resp.status} {text}")
                return

            docx_bytes = await resp.read()

    # Отправляем DOCX пользователю
    doc_name = (document.file_name or "presentation").rsplit(".", 1)[0] + "_report.docx"
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, doc_name)
    with open(tmp_path, "wb") as f:
        f.write(docx_bytes)

    await message.answer_document(FSInputFile(tmp_path, filename=doc_name))


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

