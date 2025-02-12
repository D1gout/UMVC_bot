import asyncio
from datetime import datetime, timedelta

from data import reminder_buttons
from google_docs import cmd_user_google_sheet

from db import select_reminders, delete_reminder, get_users, get_modules_from_db, get_directions_from_db


async def reminder_loop():
    from main import bot
    """Фоновая задача для отправки напоминаний"""
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        one_hour_now = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")

        reminders_to_send = await select_reminders(now)

        for reminder_id, user_id, text in reminders_to_send:
            await bot.send_message(user_id, f"🔔 Напоминание: {text}",
                                   reply_markup=reminder_buttons(user_id, one_hour_now))
            await delete_reminder(reminder_id)

        await asyncio.sleep(60)

async def update_data_in_google_sheet():
    """Добавление пользователя в Google-таблицу"""
    while True:
        user_data = await get_users()
        directions = await get_directions_from_db()
        modules = await get_modules_from_db()

        for i in range(len(user_data)):
            await cmd_user_google_sheet([user_data[i][0]], f"B{2+i}")
            await cmd_user_google_sheet([user_data[i][1]], f"C{2+i}")
            await cmd_user_google_sheet([f'https://t.me/{user_data[i][2]}'], f"D{2 + i}")
            await cmd_user_google_sheet([directions[user_data[i][3]]], f"E{2+i}")
            await cmd_user_google_sheet([", ".join([modules[module][0] for module in user_data[i][4].split(",")])], f"F{2+i}")


        await asyncio.sleep(60 * 60)
