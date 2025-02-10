import asyncio
from datetime import datetime

from data import DIRECTIONS
from google_docs import cmd_user_google_sheet

from db import select_reminders, delete_reminder, delete_scheduled_lessons, get_users


async def reminder_loop():

    from main import bot, REMINDER_BUTTONS
    """Фоновая задача для отправки напоминаний"""
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        reminders_to_send = await select_reminders(now)

        for reminder_id, user_id, text in reminders_to_send:
            await bot.send_message(user_id, f"🔔 Напоминание: {text}", reply_markup=REMINDER_BUTTONS)
            await delete_reminder(reminder_id)

        await delete_scheduled_lessons(now)
        await asyncio.sleep(60)

async def update_data_in_google_sheet():
    """Добавление пользователя в Google-таблицу"""
    while True:
        user_data = await get_users()

        for i in range(len(user_data)):
            await cmd_user_google_sheet([user_data[i][0]], f"B{2+i}")
            await cmd_user_google_sheet([user_data[i][1]], f"C{2+i}")
            await cmd_user_google_sheet([f'https://t.me/{user_data[i][2]}'], f"D{2 + i}")
            await cmd_user_google_sheet([DIRECTIONS[user_data[i][3]]], f"E{2+i}")



        await asyncio.sleep(60 * 60)
