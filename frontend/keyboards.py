# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_start_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под сообщением /start"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❓ Как это работает?", callback_data="info:howto")],
        [InlineKeyboardButton(text="⚡ Быстро по блоку", callback_data="mode:select_block")],
        [InlineKeyboardButton(text="🔥 Прожарь полностью", callback_data="mode:full_roast")]
    ])

def get_block_selector() -> InlineKeyboardMarkup:
    """Выбор конкретного блока для анализа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Информация из презентации", callback_data="block:info")],
        [InlineKeyboardButton(text="🌍 Анализ рынка", callback_data="block:market")],
        [InlineKeyboardButton(text="⚔️ Анализ конкуренции", callback_data="block:competitors")],
        [InlineKeyboardButton(text="📦 Анализ продукта", callback_data="block:product")],
        [InlineKeyboardButton(text="👥 Анализ команды", callback_data="block:team")],
        [InlineKeyboardButton(text="🏆 Итоговая оценка", callback_data="block:summary")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back:start")]
    ])

def get_result_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под готовым отчётом — только фидбек"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Круто!", callback_data="feedback:like"),
            InlineKeyboardButton(text="👎 Можно лучше", callback_data="feedback:dislike")
        ]
    ])

def get_back_to_start() -> InlineKeyboardMarkup:
    """Кнопка возврата в меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back:start")]
    ])