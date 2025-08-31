import os
import asyncio
from datetime import datetime
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
logging.basicConfig(level=logging.INFO)
# ---------------- CONFIG ----------------
API_TOKEN = "5105648336:AAHlX2hH76iKGzcDiphhaQp7BZ9QuXqmjmA"
REDIS_DSN = os.getenv("REDIS_DSN",)

from aiogram.contrib.fsm_storage.memory import MemoryStorage
storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)




# ---------------- FSM STATES ----------------
class CaloriesStates(StatesGroup):
    waiting_height = State()
    waiting_weight = State()
    waiting_age = State()
    waiting_gender = State()
    waiting_activity = State()

# ---------------- KEYBOARDS ----------------
main_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🧮 Kaloriya hisoblash", callback_data="calories")
).add(
    InlineKeyboardButton("💪 Trenirovka programma", callback_data="workout")
).add(
    InlineKeyboardButton("🍽️ Ovqat menyu", callback_data="nutrition")
)
gender_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("👨 Erkak", callback_data="gender_male"),
    InlineKeyboardButton("👩 Ayol", callback_data="gender_female"),
)

activity_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🛋️ Kam faol", callback_data="act_low"),
    InlineKeyboardButton("🚶‍♂️ O'rta faol", callback_data="act_medium"),
    InlineKeyboardButton("🏃‍♂️ Faol", callback_data="act_high"),
    InlineKeyboardButton("🏋️‍♂️ Juda faol", callback_data="act_very_high"),
)

# ---------------- HELPERS ----------------
def calculate_bmr(height_cm, weight_kg, age, gender):
    if gender == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

# ---------------- HANDLERS ----------------
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(
        "🏋️‍♂️ Xush kelibsiz!\n\n"
        "Bu bot sizga kaloriya hisoblash, workout va ovqat menyusi tuzishda yordam beradi.",
        reply_markup=main_kb
    )

@dp.callback_query_handler(lambda c: c.data == "calories")
async def cb_calories(callback_query: types.CallbackQuery):
    await CaloriesStates.waiting_height.set()
    await callback_query.message.answer("📏 Bo'yingizni kiriting (sm):")
    await callback_query.answer()

@dp.message_handler(state=CaloriesStates.waiting_height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        h = int(message.text)
    except ValueError:
        return await message.answer("Bo'yingizni raqam bilan yuboring (masalan: 175)")
    await state.update_data(height=h)
    await CaloriesStates.waiting_weight.set()
    await message.answer("⚖️ Vazningizni kiriting (kg):")

@dp.message_handler(state=CaloriesStates.waiting_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        w = float(message.text)
    except ValueError:
        return await message.answer("Vazn son bo‘lishi kerak (masalan: 70)")
    await state.update_data(weight=w)
    await CaloriesStates.waiting_age.set()
    await message.answer("🎂 Yoshingizni kiriting:")

@dp.message_handler(state=CaloriesStates.waiting_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
    except ValueError:
        return await message.answer("Yosh butun son bo‘lishi kerak.")
    await state.update_data(age=age)
    await CaloriesStates.waiting_gender.set()
    await message.answer("👤 Jinsingizni tanlang:", reply_markup=gender_kb)

@dp.callback_query_handler(lambda c: c.data.startswith("gender_"), state=CaloriesStates.waiting_gender)
async def process_gender(callback_query: types.CallbackQuery, state: FSMContext):
    gender = "male" if callback_query.data == "gender_male" else "female"
    await state.update_data(gender=gender)
    await CaloriesStates.waiting_activity.set()
    await callback_query.message.answer("🏃‍♂️ Faoliyat darajangizni tanlang:", reply_markup=activity_kb)
    await callback_query.answer()
@dp.callback_query_handler(lambda c: c.data.startswith("act_"), state=CaloriesStates.waiting_activity)
async def process_activity(callback_query: types.CallbackQuery, state: FSMContext):
    activity_map = {
        "act_low": 1.2,
        "act_medium": 1.55,
        "act_high": 1.725,
        "act_very_high": 1.9
    }
    activity_level = activity_map[callback_query.data]

    data = await state.get_data()
    bmr = calculate_bmr(
        height_cm=data["height"],
        weight_kg=data["weight"],
        age=data["age"],
        gender=data["gender"]
    )
    calories = round(bmr * activity_level)

    await callback_query.message.answer(
        f"✅ Sizning taxminiy kunlik kaloriya ehtiyojingiz:\n\n"
        f"<b>{calories} kcal</b> ⚡️"
    )
    await state.finish()
    await callback_query.answer()

# ---------------- RUN ----------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
