import os
import logging
import asyncio
import re
from datetime import datetime, timedelta

from aiogram.dispatcher import FSMContext
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage


from auto_loop import reminder_loop, update_data_in_google_sheet, remind_users_to_enter_name
from data import selected_roles
from db import select_user, insert_reminders, replace_user, get_user_modules, \
    update_user, get_lesson_schedule, update_reminders, clear_user, update_role, get_modules_from_db, \
    get_directions_from_db, add_new_lesson, get_role, add_new_module, delete_lesson, add_user_name, \
    get_modules_description, get_users
from google_docs import cmd_reminders_google_sheet, sync_module_dates, delete_column

load_dotenv()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

user_messages = {}
pending_messages = {}

class UserState(StatesGroup):
    waiting_for_full_name = State()

async def get_lesson_and_modules(user_id, message):
    user_info = await select_user(user_id)

    if user_info is None:
        await message.answer("Ошибка: сначала выберите направление!")
        return None, None, None

    selected_modules = []
    if user_info[2]:
        selected_modules = user_info[2].split(",")  # Извлекаем модули из базы

    lessons = await get_lesson_schedule(selected_modules)
    modules = await get_modules_from_db()

    return lessons, modules, selected_modules


@dp.callback_query_handler(lambda c: c.data == "finish")
async def finish_selection(callback_query: types.CallbackQuery):
    """Завершаем выбор модулей и создаём напоминания"""
    user_id = callback_query.from_user.id

    for message_id in user_messages.get(user_id, []):
        try:
            await bot.delete_message(user_id, message_id)
        except Exception:
            pass

    user_messages.pop(user_id, None)

    await bot.delete_message(user_id, callback_query.message.message_id)
    await bot.send_message(callback_query.from_user.id, "📝 Для регистрации укажи, пожалуйста, свои ФИО.\n"
                                                        "Эта информация нужна, чтобы выдать тебе персональный сертификат по итогам обучения.\n\n"
                                                        "Как отправить?\n"
                                                        "Просто напиши свои ФИО в чат в формате:\n"
                                                        "«Иванов Иван Иванович»")
    await UserState.waiting_for_full_name.set()


@dp.message_handler(state=UserState.waiting_for_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
    """Обработка ввода ФИО пользователя"""
    user_id = message.from_user.id
    full_name = message.text.strip()

    if len(full_name.split()) < 3:
        await message.answer("Пожалуйста, введите ФИО полностью")
        return

    await add_user_name(user_id, full_name)

    await state.finish()
    await message.answer(f"Спасибо, {full_name}! Регистрация завершена.")

    lessons, modules, selected_modules = await get_lesson_and_modules(user_id, message)

    if modules and selected_modules:
        for lesson_time, module in lessons:
            lesson_dt = datetime.strptime(lesson_time, "%Y-%m-%d %H:%M") - timedelta(hours=1)
            await insert_reminders(user_id, lesson_dt.strftime("%Y-%m-%d %H:%M"),
                                   f"🗓️ {modules[module][0]} в {lesson_dt.strftime('%H:%M')}")

        await bot.send_message(user_id,
                               f"Будем ждать тебя на занятиях!\n"
                               f"\n" + "\n".join(f"✔ {modules[m][0]}" for m in selected_modules))
        if lessons:
            await bot.send_message(user_id,
                                   "\n\n".join(f"🗓️ {lesson_time} - "
                                               f"{modules[module][0]}" for lesson_time, module in lessons))
        await bot.send_message(user_id, "Ты выбрал(а) крутые модули — уверены, что это хорошее начало чтобы стать лучше и круче!\n"
                                        "📌 Расписание ты можешь узнать тут - /lessons\n"
                                        "А я буду присылать тебе напоминания о занятиях, чтобы ты успел(а) подготовиться.\n"
                                        "💡 Совет: сохрани этот чат в избранное — так точно не потеряешь важные уведомления.\n"
                               )


@dp.callback_query_handler(lambda c: c.data.startswith("remind_"))
async def handle_reminder_response(callback_query: types.CallbackQuery):
    """Обработка ответа на напоминание"""
    remind_status = callback_query.data.split("_")[1]

    user_id = callback_query.data.split("_")[2]
    remind_time = callback_query.data.split("_")[3]

    try:
        if remind_status == "come":
            await cmd_reminders_google_sheet(user_id, f"Да", remind_time, "A:Z")
            await bot.send_message(callback_query.from_user.id, "Отлично! Ждём тебя на занятии. 🎉")

        elif remind_status == "skip":
            await cmd_reminders_google_sheet(user_id, f"Нет", remind_time, "A:Z")
            await bot.send_message(callback_query.from_user.id, "Жаль! Надеемся увидеть тебя в следующий раз.")

        await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    except Exception as e:
        print(f"Ошибка при отправке пользователю {user_id}: {e}")


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

    directions = await get_directions_from_db()
    keyboard = InlineKeyboardMarkup()
    for key, name in directions.items():
        keyboard.add(InlineKeyboardButton(name, callback_data=f"dir_{key}_{name}"))

    await message.answer("🎯 Уже часть команды UMVC? Жми на своё направление!\n"
                         "🌟 Только узнал о нас? Смело нажимай «Я гость» и вливайся в движение!\n\n"
                         "P.S. Следи за обновлениями в наших социальных сетях:\n"
                         "тг-канал https://t.me/+d_NKkgLy1BUxODJi\n"
                         "вк сообщество https://m.vk.com/umvcrew?from=groups", reply_markup=keyboard)


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
    await replace_user(user_id, user_tg_username, direction_key)

    # Отправляем первое сообщение с объяснением
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("➡️ Продолжить", callback_data=f"continue_{direction_key}_{direction_name}"))
    await bot.send_message(
        user_id,
        "Что такое модули?\n"
        "Это «кирпичики» твоего обучения — короткие курсы по разным направлениям: от фото и видео до психологии и первой помощи.\n"
        "✅ Каждый модуль — это практика с экспертом,\n"
        "✅ Готовые навыки для реальных проектов,\n"
        "✅ Возможность попробовать себя в новом деле!\n\n\n"
        "Как собрать свой набор?\n"
        "1️⃣ Минимум 3 модуля — чтобы погрузиться в несколько тем.\n"
        "2️⃣ Максимум не ограничен — чем больше выберешь, тем круче прокачаешься!\n"
        "3️⃣ Обязательные модули — если ты член волонтерской команды, они уже будут добавлены в твой список",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith("continue_"))
async def show_modules(callback_query: types.CallbackQuery):
    """Отображение списка модулей после нажатия на кнопку 'Продолжить'"""
    user_id = callback_query.from_user.id
    _, direction_key, direction_name = callback_query.data.split("_")

    await bot.delete_message(user_id, callback_query.message.message_id)

    modules_list = await get_modules_description()
    for module in modules_list:
        msg = await bot.send_message(user_id, module)
        user_messages.setdefault(user_id, []).append(msg.message_id)

    modules = await get_modules_from_db()

    # Фильтруем доступные модули
    available_modules = [
        (key, name) for key, (name, restrictions) in modules.items()
        if direction_key not in restrictions
    ]

    required_modules_names = []
    required_modules = []
    for module, (name, roles) in modules.items():
        if any(role in direction_key for role in roles):
            required_modules_names.append(name)
            required_modules.append(module)

    await update_user(user_id, required_modules)

    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, name in available_modules:
        keyboard.add(InlineKeyboardButton(name, callback_data=f"mod_{key}"))

    keyboard.add(InlineKeyboardButton("➕ Завершить выбор", callback_data="finish"))

    await bot.send_message(user_id,
                           f"Вы выбрали {direction_name}\n\n"
                           f"Отлично, выбери один или несколько модулей.\n"
                           f"Обязательные модули для твоего направления: {', '.join(required_modules_names)}",
                           reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("mod_"))
async def select_module(callback_query: types.CallbackQuery):
    """Добавление/удаление модуля"""
    user_id = callback_query.from_user.id
    module_key = callback_query.data.split("_", 1)[1]

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
    modules = await get_modules_from_db()
    available_modules = [
        (key, name) for key, (name, restrictions) in modules.items()
        if direction_key not in restrictions
    ]

    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, name in available_modules:
        is_selected = "✅" if key in selected_modules else ""
        keyboard.add(InlineKeyboardButton(f"{is_selected} {name}", callback_data=f"mod_{key}"))

    keyboard.add(InlineKeyboardButton("➕ Завершить выбор", callback_data="finish"))

    await bot.edit_message_reply_markup(callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("role_select_"))
async def handle_role_selection(callback_query: types.CallbackQuery):
    role_key = callback_query.data.split("_")[2]

    if role_key in selected_roles['roles']:
        selected_roles['roles'].remove(role_key)
    else:
        selected_roles['roles'].add(role_key)

    directions = await get_directions_from_db()

    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, name in directions.items():
        is_selected = "✅" if key in selected_roles['roles'] else ""
        keyboard.add(InlineKeyboardButton(f"{is_selected} {name}", callback_data=f"role_select_{key}"))

    keyboard.add(InlineKeyboardButton("➕ Завершить выбор",
                                      callback_data=f"finish_role"))
    await callback_query.answer("✅")
    await bot.edit_message_reply_markup(callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "finish_role")
async def finish_selection(callback_query: types.CallbackQuery):
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    await add_new_module(selected_roles['module_code'], selected_roles['module_name'], selected_roles['roles'])
    await callback_query.answer("Роли выбраны!")

@dp.callback_query_handler(lambda c: c.data.startswith('delete_lesson_'))
async def handle_delete_lesson(callback_query: types.CallbackQuery):
    lesson_time = callback_query.data.split("_")[3]
    key = callback_query.data.split("_")[2]

    await delete_lesson(lesson_time)
    await delete_column(lesson_time)

    keyboard = InlineKeyboardMarkup(row_width=1)
    lessons = await get_lesson_schedule([key])
    if lessons:

        for lesson in lessons:
            if lesson[0] != lesson_time:
                keyboard.add(InlineKeyboardButton(lesson[0], callback_data=f"delete_lesson_{key}_{lesson[0]}"))

    await bot.edit_message_reply_markup(
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "read_modules")
async def read_modules_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    if user_id in user_messages:
        for msg_id in user_messages[user_id]:
            await bot.delete_message(user_id, msg_id)
        del user_messages[user_id]

    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    user_id = message.from_user.id

    password = message.text.split()[1]

    if password == os.getenv("ADMIN_PASSWORD"):
        await bot.send_message(user_id, "Вы вошли в режим администратора.")
        await update_role(user_id, "admin")

    await bot.delete_message(message.from_user.id, message.message_id)



@dp.message_handler(commands=['module_info'])
async def module_info_command(message: types.Message):
    user_id = message.from_user.id

    modules_list = await get_modules_description()
    user_messages[user_id] = []  # Очищаем перед новым списком

    user_messages[user_id].append(message.message_id)
    for i, module in enumerate(modules_list):
        if i == len(modules_list) - 1:  # Для последнего модуля добавляем кнопку
            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Прочитано", callback_data="read_modules")
            )
            msg = await bot.send_message(user_id, module, reply_markup=keyboard)
        else:
            msg = await bot.send_message(user_id, module)

        user_messages[user_id].append(msg.message_id)


@dp.message_handler(commands=['lesson'])
async def lesson_command(message: types.Message):
    user_id = message.from_user.id

    if await get_role(user_id) != 'admin':
        return await bot.delete_message(message.from_user.id, message.message_id)

    msg_text = message.text.strip().replace("/lesson", "").strip()

    pattern = r"^(\w+)\s(\d{4}-\d{2}-\d{2})\s(\d{2}:\d{2})$"
    match = re.match(pattern, msg_text)
    if not match:
        modules = await get_modules_from_db()
        module_list = "\n".join([f"{key} - {name[0]}" for key, name in modules.items()])
        await message.reply(f"Неверный формат. Используйте: /lesson <module> YYYY-MM-DD HH:MM\n\n"
                            f"Доступные модули:\n{module_list}")
        return

    module_name, date, time = match.groups()
    lesson_time = f"{date} {time}"

    if await add_new_lesson(module_name, lesson_time):
        await message.reply(f"Расписание для модуля '{module_name}' на {lesson_time} добавлено.")
    else:
        await message.reply(f"Модуль '{module_name}' не найден.")


@dp.message_handler(commands=['delete_lesson'])
async def delete_lesson_command(message: types.Message):
    user_id = message.from_user.id

    if await get_role(user_id) != 'admin':
        return await bot.delete_message(message.from_user.id, message.message_id)

    # Получаем список всех занятий
    modules_list = await get_modules_from_db()

    for key, name in modules_list.items():
        lessons = await get_lesson_schedule([key])
        if lessons:

            keyboard = InlineKeyboardMarkup(row_width=1)
            for lesson in lessons:
                keyboard.add(InlineKeyboardButton(lesson[0], callback_data=f"delete_lesson_{key}_{lesson[0]}"))

            await bot.send_message(user_id, name[0], reply_markup=keyboard)



@dp.message_handler(commands=['module'])
async def add_module_command(message: types.Message):
    user_id = message.from_user.id

    if await get_role(user_id) != 'admin':
        return await bot.delete_message(message.from_user.id, message.message_id)

    params = message.text.split(" ", 2)

    if len(params) != 3:
        await message.reply("Неверный формат. Используйте: /module <module_code> <module_name>")
        return

    module_code = params[1]
    module_name = params[2]

    directions = await get_directions_from_db()

    selected_roles['module_name'] = module_name
    selected_roles['module_code'] = module_code

    keyboard = InlineKeyboardMarkup(row_width=2)
    for key, name in directions.items():
        keyboard.add(InlineKeyboardButton(name, callback_data=f"role_select_{key}"))

    keyboard.add(InlineKeyboardButton("➕ Завершить выбор",
                                      callback_data=f"finish_role"))

    await bot.send_message(message.from_user.id,
                           f"Модуль '{module_name}' добавлен! Выберите роли, для которых он будет обязательным.",
                           reply_markup=keyboard)

@dp.message_handler(commands=['lessons'])
async def get_lesson_schedule_message(message: types.Message):
    user_id = message.from_user.id

    lessons, modules, selected_modules = await get_lesson_and_modules(user_id, message)

    if lessons and modules:
        await bot.send_message(user_id,
                               "\n\n".join(f"🗓️ {lesson_time} - "
                                           f"{modules[module][0]}" for lesson_time, module in lessons))


@dp.message_handler(commands=['send_all'])
async def send_all_command(message: types.Message):
    user_id = message.from_user.id

    if await get_role(user_id) != 'admin':
        return await bot.delete_message(message.chat.id, message.message_id)

    text = message.text.replace("/send_all", "").strip()

    if not text:
        return await message.answer("Вы не ввели текст для отправки.")

    pending_messages[user_id] = text  # Сохраняем сообщение

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Подтверждаю", callback_data=f"confirm_send_all:{user_id}"))

    await message.answer(f"Вы хотите отправить это сообщение всем пользователям?\n\n{text}", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_send_all"))
async def confirm_send_all(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    if await get_role(user_id) != 'admin':
        return await callback_query.answer("У вас нет прав на это действие.", show_alert=True)

    if user_id not in pending_messages:
        return await callback_query.answer("Ошибка: сообщение не найдено.", show_alert=True)

    text = pending_messages.pop(user_id)  # Извлекаем и удаляем сообщение

    users = await get_users()
    for user in users:
        try:
            await bot.send_message(user[0], text)
        except Exception:
            pass

    await callback_query.message.edit_text("Сообщение отправлено всем пользователям.")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(reminder_loop())
    loop.create_task(update_reminders())
    loop.create_task(update_data_in_google_sheet())
    loop.create_task(sync_module_dates())
    loop.create_task(remind_users_to_enter_name())
    executor.start_polling(dp, skip_updates=True)