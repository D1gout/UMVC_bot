import asyncio

import aiosqlite

# Данные расписания занятий
LESSON_SCHEDULE = {
    "interview": "2025-02-10 18:00",
    "speech": "2025-02-11 19:00",
    "photo": "2025-02-12 17:30",
    "promotion": "2025-02-13 16:00",
    "video": "2025-02-14 15:00",
    "directing": "2025-02-15 18:00",
    "inclusion": "2025-02-16 17:00",
    "events": "2025-02-17 19:00",
    "fixiki": "2025-02-7 12:39",
}

# Функция для добавления расписания в базу данных
async def insert_schedule():
    async with aiosqlite.connect("umvc.db") as db:
        for module, lesson_time in LESSON_SCHEDULE.items():
            await db.execute('''
                INSERT OR REPLACE INTO lesson_schedule (module_name, lesson_time)
                VALUES (?, ?)
            ''', (module, lesson_time))
        await db.commit()

# Добавление данных
asyncio.run(insert_schedule())