from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

selected_roles = {
    'module_name': '',
    'module_code': '',
    'roles': set()
}

def reminder_buttons(user_id, time):
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Приду", callback_data=f"remind_come_{user_id}_{time}"),
    InlineKeyboardButton("❌ Не смогу", callback_data=f"remind_skip_{user_id}_{time}"))
    return keyboard