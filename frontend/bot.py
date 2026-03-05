import asyncio
import os
import logging
import tempfile
from io import BytesIO
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.enums import ChatAction
from dotenv import load_dotenv

from keyboards import get_start_keyboard, get_result_keyboard, get_back_to_start

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Загрузить конфиг
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "")
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 20 * 1024 * 1024))
BACKEND_TIMEOUT = int(os.getenv("BACKEND_TIMEOUT", "120"))

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# ======================================= Хранилище настроек пользователя ============================================================
user_settings = {}  # {user_id: {"mode": "full" | "block", "block": "market"}}


# =========================================== Вспомогательные функции ===============================================================

def _sanitize_filename(filename: str) -> str:
    """Базовая санитизация имени файла"""
    safe_name = Path(filename).name.replace("/", "_").replace("\\", "_")
    return safe_name if safe_name else "presentation.pdf"


async def _send_to_backend(
    session: aiohttp.ClientSession,
    file_bytes: BytesIO,
    filename: str,
    timeout: int,
    analysis_type: str = "full",
    block_type: str = None
) -> bytes:
    """Отправка файла на бэкенд с таймаутом и опциональными параметрами анализа"""
    data = aiohttp.FormData()
    data.add_field(
        "file",
        file_bytes,
        filename=filename,
        content_type="application/pdf",
    )
    
    # Добавляем параметры анализа, если бэкенд их поддерживает
    if analysis_type == "block" and block_type:
        data.add_field("analysis_type", "block")
        data.add_field("block_type", block_type)
    
    timeout_config = aiohttp.ClientTimeout(total=timeout)
    
    try:
        async with session.post(BACKEND_URL, data=data, timeout=timeout_config) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.error(f"Backend error {resp.status}: {text}")
                raise RuntimeError(f"Ошибка сервера: {resp.status}")
            return await resp.read()
    except asyncio.TimeoutError:
        logger.error(f"Timeout while calling backend after {timeout}s")
        raise
    except aiohttp.ClientError as e:
        logger.error(f"Network error calling backend: {e}")
        raise


# =========================================== Хендлеры бота =============================================================================

@dp.message(CommandStart())
@dp.message(F.text == "🚀 Начать работу")
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я BOT для генерации аналитических отчётов по Вашим Startup'ам 🤑🤙\n\n"
        f"📎 Просто отправь мне PDF-файл c презентацией твоего стартапа (!!!до {MAX_FILE_SIZE / 1024 / 1024:.0f} МБ!!!), и я верну готовый отчёт\n"
        "⏱ Обработка обычно занимает 1–3 минуты, но это того стоит 😎\n\n"
        "👇 Выбери режим работы:",
        reply_markup=get_start_keyboard()
    )


@dp.message(F.text == "🔄 Хочу ещё")
async def handle_want_more(message: Message) -> None:
    """Обработчик повторного запроса после получения отчёта"""
    await message.answer(
        "📎 Отлично! Отправляй новый PDF-файл с презентацией, и я подготовлю ещё один отчёт 👇",
        reply_markup=get_start_keyboard()
    )


@dp.message(F.document.mime_type == "application/pdf")
async def handle_pdf(message: Message) -> None:
    document = message.document
    user_id = message.from_user.id
    filename = _sanitize_filename(document.file_name or "presentation.pdf")
    
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.answer(
            "🚫 File слишком большой 🍆\n"
            f"Не отправляй мне files more, чем {MAX_FILE_SIZE / 1024 / 1024:.0f} МБ\n"
            "Заранее спасибо) ❤️‍🩹"
        )
        logger.warning(f"User {user_id} sent oversized file: {filename} ({document.file_size / 1024 / 1024:.1f} MB)")
        return

    await message.answer(f"📥 Файл «{filename}» получен! Начинаю обработку... ✨")
    
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        file = await bot.get_file(document.file_id)
        file_bytes = BytesIO()
        await bot.download_file(file.file_path, destination=file_bytes)
        file_bytes.seek(0)
    except Exception as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        await message.answer("😕 Не удалось скачать файл... Попробуй ещё раз, я верю в тебя ЧЕМПИОН 💪")
        return

    status_msg = await message.answer("⚡️ Кастую магию обработки... это займёт пару минут ✨")
    
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_DOCUMENT)

    docx_bytes = None
    
    for attempt in range(2):
        try:
            async with aiohttp.ClientSession() as session:
                docx_bytes = await _send_to_backend(
                    session=session,
                    file_bytes=file_bytes,
                    filename=filename,
                    timeout=BACKEND_TIMEOUT
                )
            break
            
        except asyncio.TimeoutError:
            logger.warning(f"Attempt {attempt + 1} failed: Timeout for user {user_id}")
            if attempt == 0:
                await status_msg.edit_text("⏳ Сервер отвечает медленно... Пробую ещё раз 🙏")
                await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(1)
                file_bytes.seek(0)
                continue
            else:
                await status_msg.edit_text("😴 Сервер задумался и не ответил вовремя... Попробуй чуть позже 🙏")
                return
                
        except RuntimeError as e:
            logger.warning(f"Attempt {attempt + 1} failed: RuntimeError - {e}")
            if attempt == 0:
                await status_msg.edit_text("🤕 Сервер капризничает... Пробую ещё раз ❤️")
                await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(1)
                file_bytes.seek(0)
                continue
            else:
                await status_msg.edit_text(f"🤕 Ой, сервер капризничает: {e}\nПопробуй ещё раз, я подожду ❤️")
                return
                
        except Exception as e:
            logger.exception(f"Attempt {attempt + 1} failed: Unexpected error for user {user_id}")
            if attempt == 0:
                await status_msg.edit_text("💥 Что-то пошло не так... Пробую ещё раз 🔧")
                await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
                await asyncio.sleep(1)
                file_bytes.seek(0)
                continue
            else:
                await status_msg.edit_text("💥 Наверное кто-то пролил пельмени на сервер( Я уже чиню! Попробуй через минутку 🔧")
                return

    if docx_bytes is None:
        logger.error(f"All attempts failed for user {user_id}, file {filename}")
        return

    base_name = Path(filename).stem
    doc_name = f"{base_name}_report.docx"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx", prefix="bot_") as tmp:
            tmp.write(docx_bytes)
            tmp_path = tmp.name
        
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_DOCUMENT)
        
        await message.answer_document(
            document=FSInputFile(tmp_path, filename=doc_name),
            caption="🎉 Готово, красавчик! Отчёт for you в DOCX уже тут 👇\nЗабирай)",
            reply_markup=get_result_keyboard()
        )
        logger.info(f"✅ Successfully processed {filename} for user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send document to user {user_id}: {e}")
        await message.answer("😅 Файл почти готов, но я споткнулся на финише... Попробуй ещё раз 🙃")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as e:
                logger.warning(f"Failed to cleanup temp file {tmp_path}: {e}")


# ================================= Callback Query Handlers ======================================================================

@dp.callback_query(F.data == "info:howto")
async def cb_info_howto(callback: CallbackQuery):
    await callback.message.edit_text(
        "🧐 **Как это работает?**\n\n"
        "1️⃣ Ты кидаешь мне PDF презентацию стартапа\n"
        "2️⃣ Я отправляю её на мощный сервер с AI\n"
        "3️⃣ Сервер анализирует всё: рынок, продукт, команду\n"
        "4️⃣ Я возвращаю тебе готовый DOCX отчёт\n\n"
        "🔥 Можно выбрать полный прожар или конкретный блок!",
        reply_markup=get_back_to_start()
    )
    await callback.answer()


# @dp.callback_query(F.data == "mode:select_block")
# async def cb_mode_block(callback: CallbackQuery):
#     user_settings[callback.from_user.id] = {"mode": "block", "block": None}
#     await callback.message.edit_text(
#         "🎯 **Выбери блок для анализа:**\n\n"
#         "Я сосредоточусь только на этом разделе, чтобы сделать его максимально подробно 🔍",
#         reply_markup=get_block_selector()
#     )
#     await callback.answer()


@dp.callback_query(F.data == "mode:full_roast")
async def cb_mode_full(callback: CallbackQuery):
    user_settings[callback.from_user.id] = {"mode": "full"}
    await callback.message.edit_text(
        "🔥 **Режим 'Прожарь полностью' активирован!**\n\n"
        "Теперь отправь PDF, и я разберу презентацию по косточкам со всех сторон 😎",
        reply_markup=get_back_to_start()
    )
    await callback.answer()


# @dp.callback_query(F.data.startswith("block:"))
# async def cb_block_select(callback: CallbackQuery):
#     block = callback.data.split(":")[1]
#     user_settings[callback.from_user.id]["block"] = block
#     
#     block_names = {
#         "info": "📄 Информация из презентации",
#         "market": "🌍 Анализ рынка",
#         "competitors": "⚔️ Анализ конкуренции",
#         "product": "📦 Анализ продукта",
#         "team": "👥 Анализ команды",
#         "summary": "🏆 Итоговая оценка"
#     }
#     
#     await callback.message.edit_text(
#         f"✅ **Выбрано:** {block_names.get(block, block)}\n\n"
#         "Отправляй PDF, и я сделаю глубокий анализ именно по этому пункту! 👇",
#         reply_markup=get_back_to_start()
#     )
#     await callback.answer()


@dp.callback_query(F.data == "back:start")
async def cb_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 Я BOT для генерации аналитических отчётов по Вашим Startup'ам 🤑🤙\n\n"
        "👇 Выбери режим работы:",
        reply_markup=get_start_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("feedback:"))
async def cb_feedback(callback: CallbackQuery):
    feedback_type = callback.data.split(":")[1]
    emoji = "👍" if feedback_type == "like" else "👎"
    
    await callback.answer(
        f"{emoji} Спасибо за фидбек! Я становлюсь лучше благодаря тебе ❤️"
    )
    
    logger.info(f"Feedback from {callback.from_user.id}: {feedback_type}")


# ================== Запуск ===========================================================================

async def main() -> None:
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Bot crashed: {e}")