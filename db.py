# Подключение к базе данных
import sqlite3

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