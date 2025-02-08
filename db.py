# Подключение к базе данных
import asyncio
import sqlite3

import aiosqlite

from data import MODULES

conn = sqlite3.connect("umvc.db")
cursor = conn.cursor()

# Таблица для напоминаний
cursor.execute('''
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    time TEXT,
    text TEXT
)
''')

# Таблица для пользовательских данных (если нужно)
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_data (
    user_id INTEGER PRIMARY KEY,
    direction TEXT,
    modules TEXT  -- Список модулей через запятую
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS lesson_schedule (
    module_name TEXT,
    lesson_time TEXT,
    PRIMARY KEY (module_name, lesson_time)
)
''')
conn.commit()

async def select_reminders(now):
    cursor.execute("SELECT id, user_id, text FROM reminders WHERE time <= ?", (now,))
    return cursor.fetchall()

async def delete_reminder(reminder_id):
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()

async def select_user(user_id):
    cursor.execute("SELECT * FROM user_data WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

async def insert_reminders(user_id, lesson_time, text):
    cursor.execute("INSERT INTO reminders (user_id, time, text) VALUES (?, ?, ?)",
                   (user_id, lesson_time, text))
    conn.commit()

async def replace_user(user_id, direction_key):
    cursor.execute("REPLACE INTO user_data (user_id, direction) VALUES (?, ?)", (user_id, direction_key))
    conn.commit()

async def update_user(user_id, modules):
    cursor.execute("UPDATE user_data SET modules = ? WHERE user_id = ?", (",".join(modules), user_id))
    conn.commit()

async def get_user_modules(user_id):
    cursor.execute("SELECT modules FROM user_data WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0].split(",") if result and result[0] else []

async def get_lesson_schedule(modules):
    cursor.execute("SELECT lesson_time, module_name FROM lesson_schedule WHERE module_name IN ({seq})"
                              .format(seq=", ".join(["?"] * len(modules))), modules)
    return cursor.fetchall()

async def clear_user(user_id):
    async with aiosqlite.connect("umvc.db") as db:
        await db.execute("DELETE FROM user_data WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
        await db.commit()

async def remove_duplicates():
    async with aiosqlite.connect("umvc.db") as db:
        await db.execute('''
        DELETE FROM reminders
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM reminders
            GROUP BY user_id, time, text
        )''')
        await db.commit()


async def update_reminders():
    while True:
        async with aiosqlite.connect("umvc.db") as db:
            # Получаем актуальное расписание занятий
            cursor = await db.execute("SELECT module_name, lesson_time FROM lesson_schedule")
            lessons = await cursor.fetchall()

            # Получаем всех пользователей, у которых есть напоминания
            cursor = await db.execute("SELECT user_id FROM user_data WHERE modules IS NOT NULL AND modules != ''")
            users = [row[0] for row in await cursor.fetchall()]

            for user_id in users:
                # Получаем выбранные пользователем модули
                cursor = await db.execute("SELECT modules FROM user_data WHERE user_id = ?", (user_id,))
                user_data = await cursor.fetchone()
                if not user_data:
                    continue

                selected_modules = user_data[0].split(",")  # Список модулей пользователя

                # Обновляем напоминания для каждого модуля пользователя
                for module, lesson_time in lessons:
                    if module in selected_modules:
                        reminder_text = f"🗓️ {MODULES[module][0]} в {lesson_time[11:16]}"

                        # Проверяем, существует ли уже такое напоминание
                        cursor = await db.execute(
                            "SELECT COUNT(*) FROM reminders WHERE user_id = ? AND time = ? AND text = ?",
                            (user_id, lesson_time, reminder_text)
                        )
                        exists = await cursor.fetchone()

                        if exists[0] == 0:  # Если напоминания нет, добавляем его
                            await db.execute(
                                "INSERT INTO reminders (user_id, time, text) VALUES (?, ?, ?)",
                                (user_id, lesson_time, reminder_text)
                            )

            await db.commit()
            await remove_duplicates()

        await asyncio.sleep(60 * 10)  # Запуск каждые 10 минут