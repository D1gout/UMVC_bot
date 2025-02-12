from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def reminder_buttons(user_id, time):
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Приду", callback_data=f"remind_come_{user_id}_{time}"),
    InlineKeyboardButton("❌ Не смогу", callback_data=f"remind_skip_{user_id}_{time}"))
    return keyboard