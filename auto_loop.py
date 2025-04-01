import asyncio
from datetime import datetime, timedelta

from data import reminder_buttons
from google_docs import cmd_user_google_sheet

from db import select_reminders, delete_reminder, get_users, get_modules_from_db, get_directions_from_db, print_user


async def reminder_loop():
    from main import bot
    """Фоновая задача для отправки напоминаний"""
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        one_hour_now = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")

        reminders_to_send = await select_reminders(now)

        for reminder_id, user_id, text in reminders_to_send:
            try:
                await bot.send_message(user_id, f"🔔 Напоминание: {text}",
                                       reply_markup=reminder_buttons(user_id, one_hour_now))
                await delete_reminder(reminder_id)
            except Exception as e:
                print(f"Ошибка при отправке пользователю {user_id}: {e}")


        await asyncio.sleep(60)

async def update_data_in_google_sheet():
    """Добавление пользователя в Google-таблицу"""
    while True:
        user_data = await get_users()
        directions = await get_directions_from_db()
        modules = await get_modules_from_db()

        for i in range(len(user_data)):
            if user_data[i][5] == 0:
                table_num = await cmd_user_google_sheet([user_data[i][0]], f"B")
                if table_num:
                    if user_data[i][1]:
                        await cmd_user_google_sheet([user_data[i][1]], f"C{table_num}")

                    if user_data[i][2]:
                        await cmd_user_google_sheet([f'https://t.me/{user_data[i][2]}'], f"D{table_num}")

                    if user_data[i][3] and user_data[i][3] in directions:
                        await cmd_user_google_sheet([directions[user_data[i][3]]], f"E{table_num}")

                    if user_data[i][4]:
                        modules_list = [modules[module][0] for module in user_data[i][4].split(",") if module in modules]
                        if modules_list:
                            await cmd_user_google_sheet([", ".join(modules_list)], f"F{table_num}")

                    await print_user(user_data[i][0])

        await asyncio.sleep(60 * 60)


async def remind_users_to_enter_name():
    from main import bot
    """Фоновая задача для напоминания пользователям ввести ФИО"""
    while True:
        user_data = await get_users()
        for user in user_data:
            user_id, full_name = user[0], user[1]

            if not full_name:
                try:
                    await bot.send_message(user_id, "Вы не ввели ФИО.\nПересоздайте аккаунт! - /start")
                except Exception as e:
                    print(f"Ошибка при отправке пользователю {user_id}: {e}")

        await asyncio.sleep(24 * 60 * 60)
