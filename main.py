import os
import logging

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardButton, InlineKeyboardMarkup

load_dotenv()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    await message.answer("Привет!")

    await message.answer("Выбери свою станцию")


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)