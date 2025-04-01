# Подключение к базе данных
import asyncio
import sqlite3
from datetime import timedelta, datetime

import aiosqlite

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
    user_name TEXT,
    direction TEXT,
    modules TEXT,
    role TEXT default 'user',
    printed INTEGER NOT NULL DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS lesson_schedule (
    module_name TEXT,
    lesson_time TEXT,
    PRIMARY KEY (module_name, lesson_time)
)
''')

cursor.execute("""
CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_code TEXT UNIQUE NOT NULL,
    module_name TEXT NOT NULL,
    description TEXT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS module_restrictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_code TEXT NOT NULL,
    role TEXT NOT NULL,
    FOREIGN KEY (module_code) REFERENCES modules (module_code)
)
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS directions (
        direction_code TEXT PRIMARY KEY,
        direction_name TEXT NOT NULL
    )
""")
conn.commit()

async def get_users():
    cursor.execute("SELECT user_id, user_name, username, direction, modules, printed FROM user_data")
    return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in cursor.fetchall()]

async def print_user(user_id):
    async with aiosqlite.connect("umvc.db") as db:
        await db.execute("UPDATE user_data SET printed = ? WHERE user_id = ?",
                       (1, user_id))
        await db.commit()


async def select_reminders(now):
    cursor.execute("SELECT id, user_id, text FROM reminders WHERE time = ?", (now,))
    return cursor.fetchall()

async def delete_reminder(reminder_id):
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()

async def select_user(user_id):
    cursor.execute("SELECT * FROM user_data WHERE user_id = ?", (user_id,))
    return cursor.fetchone()

async def insert_reminders(user_id, lesson_time, text):
    async with aiosqlite.connect("umvc.db") as db:
        await db.execute("INSERT INTO reminders (user_id, time, text) VALUES (?, ?, ?)",
                       (user_id, lesson_time, text))
        await db.commit()

async def replace_user(user_id, username, direction_key):
    cursor.execute("REPLACE INTO user_data (user_id, username, direction) VALUES (?, ?, ?)",
                   (user_id, username, direction_key))
    conn.commit()

async def add_user_name(user_id, user_name):
    cursor.execute("UPDATE user_data SET user_name = ? WHERE user_id = ?", (user_name, user_id))
    conn.commit()

async def update_user(user_id, modules):
    cursor.execute("UPDATE user_data SET modules = ? WHERE user_id = ?", (",".join(modules), user_id))
    conn.commit()

async def get_user_modules(user_id):
    cursor.execute("SELECT modules FROM user_data WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0].split(",") if result and result[0] else []

async def get_lesson_schedule(modules):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "SELECT lesson_time, module_name FROM lesson_schedule "
        "WHERE module_name IN ({seq}) AND lesson_time > ?"
        .format(seq=", ".join(["?"] * len(modules))),
        modules + [current_time]
    )
    return cursor.fetchall()

async def get_module_dates_from_db(module_name):
    async with aiosqlite.connect("umvc.db") as conn:
        cursor = await conn.cursor()

        # Выполнение асинхронного запроса
        await cursor.execute("SELECT lesson_time FROM lesson_schedule WHERE module_name = ?", (module_name,))
        dates = [row[0] for row in await cursor.fetchall()]

        return dates

async def update_role(user_id, role):
    cursor.execute("UPDATE user_data SET role = ? WHERE user_id = ?", (role, user_id))
    conn.commit()

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

async def get_modules_from_db():
    async with aiosqlite.connect("umvc.db") as conn_h:
        cursor_h = await conn_h.cursor()

        await cursor_h.execute("SELECT module_code, module_name FROM modules")
        modules = await cursor_h.fetchall()

        MODULES = {}
        for module_code, module_name in modules:
            await cursor_h.execute("SELECT role FROM module_restrictions WHERE module_code = ?", (module_code,))
            roles = [row[0] for row in await cursor_h.fetchall()]

            MODULES[module_code] = (module_name, roles)

        return MODULES

async def get_modules_description():
    async with aiosqlite.connect("umvc.db") as conn_h:
        cursor_h = await conn_h.cursor()
        await cursor_h.execute("SELECT module_name, description FROM modules")

        modules = await cursor_h.fetchall()
        return [f"{module_name} - {description}" for module_name, description in modules]

async def get_directions_from_db():
    async with aiosqlite.connect("umvc.db") as conn_h:
        cursor_h = await conn_h.cursor()

        await cursor_h.execute("SELECT direction_code, direction_name FROM directions")
        directions = await cursor_h.fetchall()

        DIRECTIONS = {code: name for code, name in directions}

        return DIRECTIONS

async def get_role(user_id):
    async with aiosqlite.connect("umvc.db") as db:
        cursor = await db.execute("SELECT role FROM user_data WHERE user_id = ?", (user_id,))
        role = await cursor.fetchone()

        return role[0]

async def add_new_lesson(module_name, lesson_time):
    async with aiosqlite.connect("umvc.db") as db:
        cursor = await db.execute("SELECT 1 FROM modules WHERE module_code = ?", (module_name,))
        module_exists = await cursor.fetchone()

        if not module_exists:
            return False

        # Добавление нового расписания
        await db.execute(
            "INSERT INTO lesson_schedule (module_name, lesson_time) VALUES (?, ?)",
            (module_name, lesson_time)
        )
        await db.commit()

        return True

async def add_new_module(module_code: str, module_name: str, required_roles: list):
    async with aiosqlite.connect("umvc.db") as db:
        cursor = await db.cursor()
        await cursor.execute(
            "INSERT INTO modules (module_code, module_name) VALUES (?, ?)",
            (module_code, module_name)
        )
        # Сохраняем роли, для которых обязательный модуль
        for role in required_roles:
            await cursor.execute(
                "INSERT INTO module_restrictions (module_code, role) VALUES (?, ?)",
                (module_code, role)
            )
        await db.commit()

async def delete_lesson(lesson_time):
    async with aiosqlite.connect("umvc.db") as db:
        await db.execute("DELETE FROM lesson_schedule WHERE lesson_time = ?", (lesson_time,))
        await db.commit()

async def update_reminders():
    while True:
        async with (aiosqlite.connect("umvc.db") as db):
            # Получаем актуальное расписание занятий
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = await db.execute("SELECT module_name, lesson_time FROM lesson_schedule WHERE lesson_time > ?",
                             (current_time,))

            lessons = await cursor.fetchall()  # Получаем все строки

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
                modules = await get_modules_from_db()

                # Обновляем напоминания для каждого модуля пользователя
                for module, lesson_time in lessons:
                    if module in selected_modules:
                        reminder_lesson_time = (datetime.strptime(lesson_time, "%Y-%m-%d %H:%M"
                                                                  ) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")

                        reminder_text = f"🗓️ {modules[module][0]} в {lesson_time[11:16]}"

                        # Проверяем, существует ли уже такое напоминание
                        cursor = await db.execute(
                            "SELECT COUNT(*) FROM reminders WHERE user_id = ? AND time = ? AND text = ?",
                            (user_id, reminder_lesson_time, reminder_text)
                        )
                        exists = await cursor.fetchone()

                        if exists[0] == 0:  # Если напоминания нет, добавляем его
                            await insert_reminders(user_id, reminder_lesson_time, reminder_text)

            await remove_duplicates()

        await asyncio.sleep(60 * 30)  # Запуск каждые 30 минут