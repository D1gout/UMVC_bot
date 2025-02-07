import os
import logging
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardButton, InlineKeyboardMarkup

from db import select_reminders, delete_reminder, select_user, insert_reminders

load_dotenv()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher(bot)

# Направления
DIRECTIONS = {
    "press": "Пресса",
    "photo": "Фотографы",
    "video": "Видеографы",
    "coord": "Координаторы",
    "guest": "Я гость"
}

# Модули с ограничениями
MODULES = {
    "interview": ("Интервью и редактура", ["press"]),
    "speech": ("Работа с речью", ["press"]),
    "photo": ("Фото", ["photo"]),
    "promotion": ("Продвижение контента", ["photo", "video"]),
    "video": ("Видео", ["video"]),
    "directing": ("Режиссура", ["video"]),
    "inclusion": ("Инклюзия", ["coord"]),
    "events": ("Организация мероприятий", ["coord"]),
    "fixiki": ("Фиксики", [])
}

# Фиксированные даты занятий (можно брать из БД)
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

# Обязательные модули
REQUIRED_MODULES = ["Первая Помощь", "Психология"]

REMINDER_BUTTONS = InlineKeyboardMarkup().add(
    InlineKeyboardButton("✅ Приду", callback_data="remind_come"),
    InlineKeyboardButton("❌ Не смогу", callback_data="remind_skip")
)

async def reminder_loop():
    """Фоновая задача для отправки напоминаний"""
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        reminders_to_send = await select_reminders(now)

        for reminder_id, user_id, text in reminders_to_send:
            await bot.send_message(user_id, f"🔔 Напоминание: {text}", reply_markup=REMINDER_BUTTONS)
            await delete_reminder(reminder_id)

        await asyncio.sleep(60)  # Проверяем каждую минуту

@dp.callback_query_handler(lambda c: c.data == "finish")
async def finish_selection(callback_query: types.CallbackQuery):
    """Завершаем выбор модулей и создаём напоминания"""
    user_id = callback_query.from_user.id

    user_info = await select_user(user_id)
    if user_info is None:
        await callback_query.answer("Ошибка: сначала выберите направление!")
        return

    selected_modules = user_info[2].split(",")  # Извлекаем модули из базы
    all_modules = ["Первая Помощь", "Психология"] + [m for m in selected_modules if m in LESSON_SCHEDULE]

    # Создаём напоминания
    for module in all_modules:
        if module in LESSON_SCHEDULE:
            lesson_time = datetime.strptime(LESSON_SCHEDULE[module], "%Y-%m-%d %H:%M")
            await insert_reminders(user_id, lesson_time.strftime("%Y-%m-%d %H:%M"),
                                   f"🗓️ {MODULES[module][0]} в {lesson_time.strftime('%H:%M')}")


    await bot.send_message(user_id,
                           f"Класс, будем ждать тебя на занятиях!\n"
                           f"Ты выбрал:\n" + "\n".join(f"✔ {MODULES[m][0]}" for m in selected_modules))

    await bot.send_message(user_id, "Я добавил напоминания о занятиях. ✅")


@dp.callback_query_handler(lambda c: c.data.startswith("remind_"))
async def handle_reminder_response(callback_query: types.CallbackQuery):
    """Обработка ответа на напоминание"""
    if callback_query.data == "remind_come":
        await bot.send_message(callback_query.from_user.id, "Отлично! Ждём тебя на занятии. 🎉")
    elif callback_query.data == "remind_skip":
        await bot.send_message(callback_query.from_user.id, "Жаль! Надеемся увидеть тебя в следующий раз.")


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    """Начало работы с ботом — выбор направления"""
    keyboard = InlineKeyboardMarkup()
    for key, name in DIRECTIONS.items():
        keyboard.add(InlineKeyboardButton(name, callback_data=f"dir_{key}"))

    await message.answer("Добро пожаловать в Академию!\nКакое направление вы выбрали?", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("dir_"))
async def choose_modules(callback_query: types.CallbackQuery):
    """Выбор модулей после направления"""
    user_id = callback_query.from_user.id
    direction_key = callback_query.data.split("_")[1]

    # Сохраняем направление
    user_data[user_id] = {"direction": direction_key, "modules": set()}

    # Фильтруем доступные модули
    available_modules = [
        (key, name) for key, (name, restrictions) in MODULES.items()
        if direction_key not in restrictions
    ]

    # Создаём клавиатуру для выбора модулей
    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, name in available_modules:
        keyboard.add(InlineKeyboardButton(name, callback_data=f"mod_{key}"))

    keyboard.add(InlineKeyboardButton("✅ Завершить выбор", callback_data="finish"))

    await bot.send_message(callback_query.from_user.id,
                           f"Отлично, выбери один или несколько модулей.\n"
                           f"Обязательные модули: {', '.join(REQUIRED_MODULES)}",
                           reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("mod_"))
async def select_module(callback_query: types.CallbackQuery):
    """Добавление/удаление модуля"""
    user_id = callback_query.from_user.id
    module_key = callback_query.data.split("_")[1]

    if user_id not in user_data:
        await callback_query.answer("Ошибка: сначала выберите направление!")
        return

    # Переключаем модуль (если есть — удаляем, если нет — добавляем)
    if module_key in user_data[user_id]["modules"]:
        user_data[user_id]["modules"].remove(module_key)
    else:
        user_data[user_id]["modules"].add(module_key)

    # Обновляем клавиатуру с выбором модулей
    direction_key = user_data[user_id]["direction"]
    available_modules = [
        (key, name) for key, (name, restrictions) in MODULES.items()
        if direction_key not in restrictions
    ]

    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, name in available_modules:
        is_selected = "✅" if key in user_data[user_id]["modules"] else ""
        keyboard.add(InlineKeyboardButton(f"{is_selected} {name}", callback_data=f"mod_{key}"))

    keyboard.add(InlineKeyboardButton("✅ Завершить выбор", callback_data="finish"))

    await bot.edit_message_reply_markup(callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == "finish")
async def finish_selection(callback_query: types.CallbackQuery):
    """Завершаем выбор модулей"""
    user_id = callback_query.from_user.id

    if user_id not in user_data:
        await callback_query.answer("Ошибка: сначала выберите направление!")
        return

    selected_modules = [MODULES[m][0] for m in user_data[user_id]["modules"]]
    all_modules = REQUIRED_MODULES + selected_modules

    await bot.send_message(user_id,
                           f"Класс, будем ждать тебя на первом занятии!\n"
                           f"Ты выбрал:\n" + "\n".join(f"✔ {mod}" for mod in all_modules))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(reminder_loop())
    executor.start_polling(dp, skip_updates=True)