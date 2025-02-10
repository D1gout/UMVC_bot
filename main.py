import os
import logging
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from auto_loop import reminder_loop, update_data_in_google_sheet
from data import MODULES, DIRECTIONS, REQUIRED_MODULES
from db import select_user, insert_reminders, replace_user, get_user_modules, \
    update_user, get_lesson_schedule, update_reminders, clear_user

load_dotenv()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher(bot)



REMINDER_BUTTONS = InlineKeyboardMarkup().add(
    InlineKeyboardButton("✅ Приду", callback_data="remind_come"),
    InlineKeyboardButton("❌ Не смогу", callback_data="remind_skip")
)

@dp.callback_query_handler(lambda c: c.data == "finish")
async def finish_selection(callback_query: types.CallbackQuery):
    """Завершаем выбор модулей и создаём напоминания"""
    user_id = callback_query.from_user.id

    user_info = await select_user(user_id)
    if user_info is None:
        await callback_query.answer("Ошибка: сначала выберите направление!")
        return

    selected_modules = []
    if user_info[2]:
        selected_modules = user_info[2].split(",")  # Извлекаем модули из базы
    selected_modules += ['first_aid', 'psych']

    lessons = await get_lesson_schedule(selected_modules)

    # Создаём напоминания
    for lesson_time, module in lessons:
        lesson_dt = datetime.strptime(lesson_time, "%Y-%m-%d %H:%M")
        await insert_reminders(user_id, lesson_dt.strftime("%Y-%m-%d %H:%M"),
                               f"🗓️ {MODULES[module][0]} в {lesson_dt.strftime('%H:%M')}")

    await bot.delete_message(user_id, callback_query.message.message_id)
    await bot.send_message(user_id,
                           f"Класс, будем ждать тебя на занятиях!\n"
                           f"Ты выбрал:\n" + "\n".join(f"✔ {MODULES[m][0]}" for m in selected_modules))
    if lessons:
        await bot.send_message(user_id,
                               "\n\n".join(f"🗓️ {lesson_time} - "
                                           f"{MODULES[module][0]}" for lesson_time, module in lessons))
    await bot.send_message(user_id, "Добавлены напоминания о занятиях. ✅")


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
    user_id = message.from_user.id

    existing_user = await select_user(user_id)

    if existing_user:
        # Спрашиваем, хочет ли пользователь пересоздать аккаунт
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Пересоздать аккаунт", callback_data="reset_account"))
        keyboard.add(InlineKeyboardButton("❌ Оставить как есть", callback_data="cancel_reset"))

        await message.answer("Вы уже зарегистрированы. Хотите пересоздать аккаунт?", reply_markup=keyboard)
        return

    # Если пользователя нет — предлагаем выбрать направление
    keyboard = InlineKeyboardMarkup()
    for key, name in DIRECTIONS.items():
        keyboard.add(InlineKeyboardButton(name, callback_data=f"dir_{key}_{name}"))

    await message.answer("Добро пожаловать в Академию!\nКакое направление вы выбрали?", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "reset_account")
async def reset_account(callback_query: types.CallbackQuery):
    """Пересоздание аккаунта"""
    user_id = callback_query.from_user.id

    await clear_user(user_id)

    await callback_query.answer("✅ Ваш аккаунт был сброшен. Начните регистрацию заново.")
    await bot.delete_message(user_id, callback_query.message.message_id)
    await start(callback_query.message)  # Запускаем процесс заново

@dp.callback_query_handler(lambda c: c.data == "cancel_reset")
async def cancel_reset(callback_query: types.CallbackQuery):
    """Отмена пересоздания аккаунта"""
    await callback_query.answer("Оставляем всё как есть! 🎉")

@dp.callback_query_handler(lambda c: c.data.startswith("dir_"))
async def choose_modules(callback_query: types.CallbackQuery):
    """Выбор модулей после направления"""
    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.full_name
    user_tg_username = callback_query.from_user.username
    direction_key = callback_query.data.split("_")[1]
    direction_name = callback_query.data.split("_")[2]

    # Сохраняем направление пользователя в БД
    await replace_user(user_id, user_name, user_tg_username, direction_key)

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

    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    await bot.send_message(callback_query.from_user.id,
                           f"Вы выбрали 🚦 {direction_name} 🚦\n\n"
                           f"Отлично, выбери один или несколько модулей.\n"
                           f"Обязательные модули: {', '.join(REQUIRED_MODULES)}",
                           reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("mod_"))
async def select_module(callback_query: types.CallbackQuery):
    """Добавление/удаление модуля"""
    user_id = callback_query.from_user.id
    module_key = callback_query.data.split("_")[1]

    # Проверяем, выбрал ли пользователь направление
    user_info = await select_user(user_id)
    if not user_info:
        await callback_query.answer("Ошибка: сначала выберите направление!")
        return

    # Получаем текущие выбранные модули пользователя
    selected_modules = await get_user_modules(user_id)

    # Переключаем модуль (если есть — удаляем, если нет — добавляем)
    if module_key in selected_modules:
        selected_modules.remove(module_key)
    else:
        selected_modules.append(module_key)

    # Обновляем выбранные модули в базе данных
    await update_user(user_id, selected_modules)

    # Обновляем клавиатуру с выбором модулей
    direction_key = user_info[1]
    available_modules = [
        (key, name) for key, (name, restrictions) in MODULES.items()
        if direction_key not in restrictions
    ]

    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, name in available_modules:
        is_selected = "✅" if key in selected_modules else ""
        keyboard.add(InlineKeyboardButton(f"{is_selected} {name}", callback_data=f"mod_{key}"))

    keyboard.add(InlineKeyboardButton("✅ Завершить выбор", callback_data="finish"))

    await bot.edit_message_reply_markup(callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(reminder_loop())
    loop.create_task(update_reminders())
    loop.create_task(update_data_in_google_sheet())
    executor.start_polling(dp, skip_updates=True)