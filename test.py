from aiogram.types import ContentType
from aiogram import types
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

API_TOKEN = "8437567401:AAFec2OceXEKQO0r0O2GWucBCdpwJWBVExI"  # .env da saqlang

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

@dp.message_handler(content_types=ContentType.VIDEO_NOTE)
async def handle_video(message: types.Message):
    print(True)
    video_note_object = message.video_note

    # file_id ni olish
    file_id = video_note_object.file_id

    # Xabarga javob yuborish
    await message.reply(f"Men video qabul qildim!\nFile ID: {file_id}")
    print(file_id)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)