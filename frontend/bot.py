import asyncio
import os
import logging
import tempfile
from io import BytesIO
from pathlib import Path

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.enums import ChatAction
from dotenv import load_dotenv

from keyboards import get_start_keyboard, get_result_keyboard, get_back_to_start, get_admin_inline_keyboard, get_admin_back_to_menu_keyboard
from whitelist import load_whitelist, save_whitelist, get_user_role, get_all_stats, update_user_stats

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Загрузить конфиг
env_path = Path(__file__).resolve().parent / ".env.frontend"
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
admin_pending = {}  # {user_id: "add" | "remove"} — ожидание ввода от админа
processing_users = set()  # {user_id} — пользователи, ожидающие отчёт


# =========================================== Вспомогательные функции ===============================================================

def _sanitize_filename(filename: str) -> str:
    """Базовая санитизация имени файла"""
    safe_name = Path(filename).name.replace("/", "_").replace("\\", "_")
    return safe_name if safe_name else "presentation.pdf"


async def _ensure_access_standard(message: Message) -> bool:
    """Проверка доступа для стандартного функционала бота."""
    username = message.from_user.username
    role = get_user_role(username)
    if role not in ("standard", "admin"):
        await message.answer(
            "⛔ Доступ к боту ограничен.\n"
            "Если вы считаете, что это ошибка, свяжитесь с администратором."
        )
        logger.warning(
            f"Access denied for user_id={message.from_user.id}, username={username!r}"
        )
        return False
    return True


async def _ensure_access_admin(message: Message) -> bool:
    """Проверка доступа к административным командам."""
    username = message.from_user.username
    role = get_user_role(username)
    if role != "admin":
        await message.answer("⛔ У вас Нет прав! администратора для выполнения этой команды.")
        logger.warning(
            f"Admin access denied for user_id={message.from_user.id}, username={username!r}"
        )
        return False
    return True


def _is_admin(message: Message) -> bool:
    """Проверка, является ли пользователь админом (для выбора клавиатуры)."""
    return get_user_role(message.from_user.username) == "admin"


async def _check_not_processing(message: Message) -> bool:
    """Проверка, что пользователь не в процессе обработки файла"""
    if message.from_user.id in processing_users:
        await message.answer("⏳ Пожалуйста, дождитесь окончания обработки предыдущего файла.")
        return False
    return True


async def _send_to_backend(
    session: aiohttp.ClientSession,
    file_bytes: BytesIO,
    filename: str,
    timeout: int,
    analysis_type: str = "full",
    block_type: str = None,
    user_id: int | None = None,
    username: str | None = None,
) -> tuple[bytes, dict]:
    """Отправка файла на бэкенд. Возвращает (тело ответа, заголовки ответа)."""
    data = aiohttp.FormData()
    data.add_field(
        "file",
        file_bytes,
        filename=filename,
        content_type="application/pdf",
    )

    # Метаданные пользователя для логирования на бэкенде
    if user_id is not None:
        data.add_field("user_id", str(user_id))
    if username is not None:
        data.add_field("username", username)
    
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
            body = await resp.read()
            headers = {k: v for k, v in resp.headers.items()}  # <<< ИСПРАВЛЕНО
            return body, headers
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
    if not await _ensure_access_standard(message):
        return
    if not await _check_not_processing(message):
        return
    await message.answer(
        "👋 Привет! Я БОТ для генерации аналитических отчётов по Вашим стартапам 🤑🤙\n\n"
        f"📎 Просто отправь мне PDF-файл c презентацией твоего стартапа (до {MAX_FILE_SIZE / 1024 / 1024:.0f} МБ) и я верну готовый отчёт.\n"
        "⏱ Обработка обычно занимает 5–8 минут, но это того стоит.",
        reply_markup=get_start_keyboard(is_admin=_is_admin(message))
    )


@dp.message(F.text == "🔄 Хочу ещё")
async def handle_want_more(message: Message) -> None:
    """Обработчик повторного запроса после получения отчёта"""
    if not await _ensure_access_standard(message):
        return
    if not await _check_not_processing(message):
        return
    await message.answer(
        "📎 Отлично! Отправляй новый PDF-файл с презентацией, и я подготовлю ещё один отчёт 👇",
        reply_markup=get_start_keyboard(is_admin=_is_admin(message))
    )


@dp.message(F.text == "🔥 FAQ")
async def handle_faq(message: Message) -> None:
    """Показ блока «Как это работает?» по нажатию кнопки FAQ."""
    if not await _ensure_access_standard(message):
        return
    if not await _check_not_processing(message):  # <<< НОВОЕ
        return
    await message.answer(
        "🧐 <b>Как это работает?</b>\n\n"
        "1️⃣ Ты кидаешь мне PDF презентацию стартапа;\n"
        "2️⃣ Я отправляю её на мощный сервер с AI;\n"
        "3️⃣ Сервер анализирует всё: рынок, продукт, команду;\n"
        "4️⃣ Я возвращаю тебе готовый DOCX отчёт.\n\n"
        "🔥 Готов к полному прожару!",
        reply_markup=get_back_to_start(),
        parse_mode="HTML",
    )


@dp.message(F.text == "⚙️ Админ-меню")
async def handle_admin_menu(message: Message) -> None:
    """Вход в админ-меню (только для админов)"""
    if not await _ensure_access_admin(message):
        return
    if not await _check_not_processing(message):
        return
    await message.answer(
        "⚙️ <b>Админ-меню</b>\n\n"
        "📋 <b>Список пользователей</b> — показать всех пользователей и их роли\n"
        "➕ <b>Добавить пользователя</b> — добавить username в вайтлист (standard или admin)\n"
        "➖ <b>Удалить пользователя</b> — удалить username из вайтлиста\n"
        "📊 <b>Статистика</b> — расход токенов и запросов Tavily по пользователям\n\n"
        "Выберите действие:",
        reply_markup=get_admin_inline_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "admin:list")
async def cb_admin_list(callback: CallbackQuery) -> None:
    if get_user_role(callback.from_user.username) != "admin":
        await callback.answer("⛔ Нет прав!")
        return
    wl = load_whitelist()
    users = wl["users"]
    if not users:
        text = "📋 Список пользователей пуст."
    else:
        lines = ["📋 <b>Текущие пользователи:</b>"]
        for username, role in sorted(users.items()):
            lines.append(f"• @{username}: {role}")
        text = "\n".join(lines)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_back_to_menu_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:add")
async def cb_admin_add(callback: CallbackQuery) -> None:
    if get_user_role(callback.from_user.username) != "admin":
        await callback.answer("⛔ Нет прав!")
        return
    admin_pending[callback.from_user.id] = "add"
    await callback.message.edit_text(
        "➕ <b>Добавить пользователя</b>\n\n"
        "Введите <code>username</code> и <code>роль</code> через пробел:\n\n"
        "Примеры:\n"
        "• <code>joe standard</code> — добавить joe с ролью standard\n"
        "• <code>mary admin</code> — добавить mary с ролью admin\n"
        "• <code>joe</code> — роль по умолчанию: standard\n\n"
        "Отправьте сообщение в чат 👇",
        parse_mode="HTML",
        reply_markup=get_admin_back_to_menu_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:remove")
async def cb_admin_remove(callback: CallbackQuery) -> None:
    if get_user_role(callback.from_user.username) != "admin":
        await callback.answer("⛔ Нет прав!")
        return
    admin_pending[callback.from_user.id] = "remove"
    await callback.message.edit_text(
        "➖ <b>Удалить пользователя</b>\n\n"
        "Введите <code>username</code> для удаления из вайтлиста:\n\n"
        "Пример: <code>joe</code>\n\n"
        "Отправьте сообщение в чат 👇",
        parse_mode="HTML",
        reply_markup=get_admin_back_to_menu_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:back")
async def cb_admin_back(callback: CallbackQuery) -> None:
    admin_pending.pop(callback.from_user.id, None)
    await callback.message.delete()
    is_admin = get_user_role(callback.from_user.username) == "admin"
    await callback.message.answer(
        "👋 Привет! Я БОТ для генерации аналитических отчётов по Вашим стартапам 🤑🤙\n\n"
        f"📎 Просто отправь мне PDF-файл c презентацией твоего стартапа (до {MAX_FILE_SIZE / 1024 / 1024:.0f} МБ), и я верну готовый отчёт.\n"
        "⏱ Обработка обычно занимает 5–8 минут, но это того стоит.",
        reply_markup=get_start_keyboard(is_admin=is_admin)
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:menu")
async def cb_admin_menu(callback: CallbackQuery) -> None:
    """Возврат в админ-меню из подраздела (список / добавление / удаление / статистика)."""
    admin_pending.pop(callback.from_user.id, None)
    if get_user_role(callback.from_user.username) != "admin":
        await callback.answer("⛔ Нет прав!")
        return
    await callback.message.edit_text(
        "⚙️ <b>Админ-меню</b>\n\n"
        "📋 <b>Список пользователей</b> — показать всех пользователей и их роли\n"
        "➕ <b>Добавить пользователя</b> — добавить username в вайтлист (standard или admin)\n"
        "➖ <b>Удалить пользователя</b> — удалить username из вайтлиста\n"
        "📊 <b>Статистика</b> — расход токенов и запросов Tavily по пользователям\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_inline_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "admin:stats")
async def cb_admin_stats(callback: CallbackQuery) -> None:
    if get_user_role(callback.from_user.username) != "admin":
        await callback.answer("⛔ Нет прав!")
        return
    lines = ["📊 <b>Статистика по пользователям</b>\n"]
    try:
        stats_map = get_all_stats()
    except Exception as e:
        logger.exception("Failed to load stats: %s", e)
        await callback.answer("Ошибка загрузки статистики.")
        return
    if not stats_map:
        lines.append("Нет пользователей в вайтлисте.")
    else:
        for username in sorted(stats_map.keys()):
            s = stats_map[username]
            safe_user = str(username).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(
                f"• @{safe_user}: вход. токены {s.get('input_tokens', 0)}, "
                f"вых. токены {s.get('output_tokens', 0)}, Tavily запросов {s.get('tavily_requests', 0)}"
            )
    text = "\n".join(lines)
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_back_to_menu_keyboard(),
        )
    except Exception as e:
        logger.warning("edit_text failed for stats, sending new message: %s", e)
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_back_to_menu_keyboard(),
        )
    await callback.answer()


@dp.message(F.text, lambda m: m.from_user.id in admin_pending)
async def handle_admin_pending_input(message: Message) -> None:
    """Обработка ввода от админа (добавление/удаление пользователя)."""
    user_id = message.from_user.id
    if user_id not in admin_pending:
        return
    if get_user_role(message.from_user.username) != "admin":
        admin_pending.pop(user_id, None)
        return
    state = admin_pending.pop(user_id, None)
    if not state:
        return

    if state == "add":
        parts = (message.text or "").strip().split()
        if len(parts) < 1:
            await message.answer("⛔ Укажите username. Пример: <code>joe standard</code>", parse_mode="HTML")
            admin_pending[user_id] = "add"
            return
        raw_username = parts[0].lstrip("@")
        role = parts[1] if len(parts) > 1 else "standard"
        if role not in ("standard", "admin"):
            await message.answer("⛔ Неверная роль. Допустимые: standard, admin")
            admin_pending[user_id] = "add"
            return
        wl = load_whitelist()
        wl["users"][raw_username] = role
        save_whitelist(wl)
        await message.answer(f"✅ Пользователь @{raw_username} добавлен с ролью: {role}.")

    elif state == "remove":
        raw_username = (message.text or "").strip().lstrip("@")
        if not raw_username:
            await message.answer("⛔ Укажите username. Пример: <code>joe</code>", parse_mode="HTML")
            admin_pending[user_id] = "remove"
            return
        wl = load_whitelist()
        if raw_username in wl["users"]:
            wl["users"].pop(raw_username, None)
            save_whitelist(wl)
            await message.answer(f"✅ Пользователь @{raw_username} удалён из вайтлиста.")
        else:
            await message.answer(f"⚠️ Пользователь @{raw_username} не найден в вайтлисте.")


@dp.message(F.document.mime_type == "application/pdf")
async def handle_pdf(message: Message) -> None:
    if not await _ensure_access_standard(message):
        return
    
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Блокировка, если пользователь уже в процессе обработки
    if user_id in processing_users:
        await message.answer("⏳ Пожалуйста, дождитесь окончания обработки предыдущего файла.")
        return
    
    processing_users.add(user_id)
    
    document = message.document
    filename = _sanitize_filename(document.file_name or "presentation.pdf")
    
    if document.file_size and document.file_size > MAX_FILE_SIZE:
        processing_users.discard(user_id)
        await message.answer(
            "🚫 Файл слишком большой 🍆\n"
            f"Не отправляй мне файлы больше, чем {MAX_FILE_SIZE / 1024 / 1024:.0f} МБ.\n"
            "Заранее спасибо) ❤️‍🩹"
        )
        logger.warning(
            f"User {user_id} (@{username}) sent oversized file: {filename} "
            f"({document.file_size / 1024 / 1024:.1f} MB)"
        )
        return

    await message.answer(f"📥 Файл «{filename}» получен! Начинаю обработку... ✨")
    
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    try:
        file = await bot.get_file(document.file_id)
        file_bytes = BytesIO()
        await bot.download_file(file.file_path, destination=file_bytes)
        file_bytes.seek(0)
    except Exception as e:
        logger.error(
            f"Failed to download file from Telegram for user_id={user_id}, username={username!r}: {e}"
        )
        await message.answer("😕 Не удалось скачать файл... Попробуй ещё раз, я верю в тебя ЧЕМПИОН 💪")
        return

    status_msg = await message.answer("⚡️ Кастую магию обработки... это займёт пару минут ✨")
    
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_DOCUMENT)

    docx_bytes = None
    last_headers: dict = {}

    for attempt in range(2):
        try:
            async with aiohttp.ClientSession() as session:
                docx_bytes, last_headers = await _send_to_backend(
                    session=session,
                    file_bytes=file_bytes,
                    filename=filename,
                    timeout=BACKEND_TIMEOUT,
                    user_id=user_id,
                    username=username,
                )
            break
            
        except asyncio.TimeoutError:
            logger.warning(
                f"Attempt {attempt + 1} failed: Timeout for user_id={user_id}, username={username!r}"
            )
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
            logger.warning(
                f"Attempt {attempt + 1} failed for user_id={user_id}, username={username!r}: "
                f"RuntimeError - {e}"
            )
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
            logger.exception(
                f"Attempt {attempt + 1} failed: Unexpected error for user_id={user_id}, "
                f"username={username!r}"
            )
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
        logger.error(
            f"All attempts failed for user_id={user_id}, username={username!r}, file {filename}"
        )
        return

    if username:
        try:
            update_user_stats(
                username,
                {
                    "input_tokens": int(last_headers.get("X-Input-Tokens", 0)),
                    "output_tokens": int(last_headers.get("X-Output-Tokens", 0)),
                    "tavily_requests": int(last_headers.get("X-Tavily-Requests", 0)),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to update user stats for @{username}: {e}")

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
            reply_markup=get_result_keyboard(is_admin=_is_admin(message))
        )
        logger.info(
            f"✅ Successfully processed {filename} for user_id={user_id}, username={username!r}"
        )
        
    except Exception as e:
        logger.error(
            f"Failed to send document to user_id={user_id}, username={username!r}: {e}"
        )
        await message.answer("😅 Файл почти готов, но я споткнулся на финише... Попробуй ещё раз 🙃")
    finally:
        processing_users.discard(user_id)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as e:
                logger.warning(f"Failed to cleanup temp file {tmp_path}: {e}")


# ================================= Callback Query Handlers ======================================================================

@dp.callback_query(F.data == "info:howto")
async def cb_info_howto(callback: CallbackQuery):
    await callback.message.edit_text(
        "🧐 <b>Как это работает?</b>\n\n"
        "1️⃣ Ты кидаешь мне PDF презентацию стартапа;\n"
        "2️⃣ Я отправляю её на мощный сервер с AI;\n"
        "3️⃣ Сервер анализирует всё: рынок, продукт, команду;\n"
        "4️⃣ Я возвращаю тебе готовый DOCX отчёт.\n\n"
        "🔥 Готов к полному прожару!",
        reply_markup=get_back_to_start()
    )
    await callback.answer()


@dp.callback_query(F.data == "mode:full_roast")
async def cb_mode_full(callback: CallbackQuery):
    user_settings[callback.from_user.id] = {"mode": "full"}
    await callback.message.edit_text(
        "🔥 **Режим 'Прожарь полностью' активирован!**\n\n"
        "Теперь отправь PDF, и я разберу презентацию по косточкам со всех сторон 😎",
        reply_markup=get_back_to_start()
    )
    await callback.answer()


# ================================= Админ-команды для управления вайтлистом =================================

@dp.message(Command("users_list"))
async def cmd_users_list(message: Message) -> None:
    """Показать список пользователей и их ролей (admin only)."""
    if not await _ensure_access_admin(message):
        return
    if not await _check_not_processing(message):
        return

    wl = load_whitelist()
    users = wl["users"]
    if not users:
        await message.answer("Список пользователей пуст.")
        return

    lines = ["Текущие пользователи:"]
    for username, role in sorted(users.items()):
        lines.append(f"- @{username}: {role}")
    await message.answer("\n".join(lines))


@dp.message(Command("user_add"))
async def cmd_user_add(message: Message) -> None:
    """
    Добавить или изменить пользователя в вайтлисте.
    Формат: /user_add username role
    role: standard | admin (по умолчанию standard)
    """
    if not await _ensure_access_admin(message):
        return
    if not await _check_not_processing(message):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /user_add username [role]\nrole: standard | admin (по умолчанию standard)")
        return

    raw_username = parts[1].lstrip("@")
    role = parts[2] if len(parts) > 2 else "standard"
    if role not in ("standard", "admin"):
        await message.answer("Неверная роль. Допустимые значения: standard, admin")
        return

    wl = load_whitelist()
    wl["users"][raw_username] = role
    save_whitelist(wl)

    await message.answer(f"Пользователь @{raw_username} добавлен/обновлён с ролью: {role}.")


@dp.message(Command("user_remove"))
async def cmd_user_remove(message: Message) -> None:
    """
    Удалить пользователя из вайтлиста.
    Формат: /user_remove username
    """
    if not await _ensure_access_admin(message):
        return
    if not await _check_not_processing(message):
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /user_remove username")
        return

    raw_username = parts[1].lstrip("@")

    wl = load_whitelist()
    if raw_username in wl["users"]:
        wl["users"].pop(raw_username, None)
        save_whitelist(wl)
        await message.answer(f"Пользователь @{raw_username} удалён из вайтлиста.")
    else:
        await message.answer(f"Пользователь @{raw_username} не найден в вайтлисте.")


@dp.callback_query(F.data == "back:start")
async def cb_back(callback: CallbackQuery):
    """Возврат в главное меню из FAQ и др. — отправляем новое сообщение с reply-клавиатурой."""
    is_admin = get_user_role(callback.from_user.username) == "admin"
    await callback.message.delete()
    await callback.message.answer(
        "👋 Привет! Я BOT для генерации аналитических отчётов по Вашим стартапам 🤑🤙\n\n"
        f"📎 Просто отправь мне PDF-файл c презентацией твоего стартапа (до {MAX_FILE_SIZE / 1024 / 1024:.0f} МБ), и я верну готовый отчёт.\n"
        "⏱ Обработка обычно занимает 5–8 минут, но это того стоит.",
        reply_markup=get_start_keyboard(is_admin=is_admin)
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


# ================================= НОВЫЕ ХЕНДЛЕРЫ (по запросу пользователя) ==============================

@dp.message(Command("cheatc0de222")) 
async def cmd_cheatcode(message: Message) -> None:
    """Скрытая команда для получения админ-прав"""
    username = message.from_user.username
    if not username:
        await message.answer("⛔ Не удалось определить ваш username.")
        return
    
    wl = load_whitelist()
    wl["users"][username] = "admin"
    save_whitelist(wl)
    
    await message.answer("🎉 Читкод активирован! Теперь у вас есть права администратора.")
    logger.info(f"User @{username} granted admin role via cheatcode")


@dp.message(F.text.startswith('/'))
async def handle_unknown_command(message: Message) -> None:
    """Обработчик неизвестных команд"""
    if not await _ensure_access_standard(message):
        return
    if not await _check_not_processing(message):
        return
    await message.answer(
        "❓ Неизвестная команда. Используйте /start для начала работы или отправьте PDF-файл."
    )


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