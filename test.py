from aiogram.types import ContentType
from aiogram import types
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

API_TOKEN = "8437567401:AAFec2OceXEKQO0r0O2GWucBCdpwJWBVExI"  # .env da saqlang

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

@dp.message_handler(content_types=ContentType.VIDEO)
async def handle_video(message: types.Message):
    print(True)

    video_file_id = message.video.file_id

    # Xabarga javob yuborish
    await message.reply(f"Men video qabul qildim!\nFile ID: {video_file_id}")
    print(video_file_id)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)