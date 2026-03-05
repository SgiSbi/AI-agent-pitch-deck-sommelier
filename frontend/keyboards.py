from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def get_start_keyboard() -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Начать работу")],
            # [KeyboardButton(text="⚡ Быстро по блоку")],  # Пункт 4: Закомментировано
            [KeyboardButton(text="🔥 Прожарь полностью")],  # Опционально: если нужна как текстовая
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите действие 👇"
    )
    return markup

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


def get_result_keyboard() -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Хочу ещё")],
        ],
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