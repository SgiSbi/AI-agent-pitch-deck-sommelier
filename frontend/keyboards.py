from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

def get_start_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🚀 Начать работу")],
        [KeyboardButton(text="🔥 FAQ")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Админ-меню")])
    markup = ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие 👇"
    )
    return markup


def get_admin_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin:list")],
        [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="admin:add")],
        [InlineKeyboardButton(text="➖ Удалить пользователя", callback_data="admin:remove")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🗑️ Очистить временные файлы", callback_data="admin:cleanup")],
        [InlineKeyboardButton(text="↩️ Назад в меню", callback_data="admin:back")],
    ])


def get_admin_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад в админ-меню» для подразделов."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад в админ-меню", callback_data="admin:menu")],
    ])

# def get_block_selector() -> InlineKeyboardMarkup:
#     """Выбор конкретного блока для анализа"""
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="📄 Информация из презентации", callback_data="block:info")],
#         [InlineKeyboardButton(text="🌍 Анализ рынка", callback_data="block:market")],
#         [InlineKeyboardButton(text="⚔️ Анализ конкуренции", callback_data="block:competitors")],
#         [InlineKeyboardButton(text="📦 Анализ продукта", callback_data="block:product")],
#         [InlineKeyboardButton(text="👥 Анализ команды", callback_data="block:team")],
#         [InlineKeyboardButton(text="🏆 Итоговая оценка", callback_data="block:summary")],
#         [InlineKeyboardButton(text="↩️ Назад", callback_data="back:start")]
#     ])


def get_result_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="🔄 Хочу ещё")]]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Админ-меню")])
    markup = ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return markup


def get_feedback_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Круто!", callback_data="feedback:like"),
            InlineKeyboardButton(text="👎 Можно лучше", callback_data="feedback:dislike")
        ]
    ])


def get_back_to_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back:start")]
    ])