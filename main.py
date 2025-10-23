import os
import django
# ------------- CONNECT DJANGO -------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fitness_backend.settings")
django.setup()
from calories.models import User, CalorieRecord
from asgiref.sync import sync_to_async
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

import logging
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ContentType
from aiogram.utils import executor

scheduler = AsyncIOScheduler()


# ------------- CONFIG -------------
logging.basicConfig(level=logging.INFO)
API_TOKEN = "8437567401:AAFec2OceXEKQO0r0O2GWucBCdpwJWBVExI"  # .env da saqlang
if API_TOKEN == "REPLACE_ME":
    logging.warning("⚠️ BOT_TOKEN o'rnatilmagan. .env orqali o'rnating: BOT_TOKEN=...")
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())


async def on_startup_notify(dp):
    # Bu funksiya loop ishga tushganidan keyin chaqiriladi
    print("Bot ishga tushdi. Scheduler boshlanmoqda...")
    scheduler.start()
    print("Scheduler muvaffaqiyatli boshlandi.")
# ------------- STATES -------------
class CaloriesStates(StatesGroup):
    waiting_height = State()
    waiting_weight = State()
    waiting_age = State()
    waiting_gender = State()
    waiting_activity = State()
    waiting_goal = State()

# ------------- KEYBOARDS -------------
main_kb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("🧮 Kaloriya hisoblash", callback_data="calories")
).add(
    InlineKeyboardButton("💪 Trenirovka programma", callback_data="workout")
).add(
    InlineKeyboardButton("🍽️ Ovqat menyu", callback_data="nutrition")
)

gender_kb = InlineKeyboardMarkup().row(
    InlineKeyboardButton("👨 Erkak", callback_data="gender_male"),
    InlineKeyboardButton("👩 Ayol", callback_data="gender_female"),
)

caloriya_cb = InlineKeyboardMarkup().add(
    InlineKeyboardButton("Mahsulotlar ro'yxati📃", web_app=types.WebAppInfo(
        url="https://docs.google.com/spreadsheets/d/17tcmlbq5e1SzyJ47BeOfw5gIc_owyNFoJ9ZOPTZ7Vo0/edit?usp=sharing"
    ))
)

# Faoliyat koeffitsientlari (siz bergan diapazon bilan)
ACTIVITY_LEVELS: Dict[str, Tuple[str, float]] = {
    "act_sedentary": ("🛋️ Juda past faollik", 1.2),
    "act_light":     ("🚶‍♂️ Yengil faollik", 1.375),
    "act_medium":    ("🏃‍♂️ O‘rtacha faollik", 1.55),
    "act_high":      ("🏋️‍♂️ Yuqori faollik", 1.725),
    "act_athlete":   ("🏆 Professional sportchilar", 1.9),
}


activity_kb = InlineKeyboardMarkup(row_width=1)
for cb, (label, _) in ACTIVITY_LEVELS.items():
    activity_kb.insert(InlineKeyboardButton(label, callback_data=cb))

goal_kb = InlineKeyboardMarkup()

goal_kb.add(InlineKeyboardButton("⬇️ Ozish", callback_data="goal_cut"))
goal_kb.add(InlineKeyboardButton("↔️ Formani ushlash", callback_data="goal_maintain"))
goal_kb.add(InlineKeyboardButton("⬆️ Vazn olish", callback_data="goal_bulk"))
# .row(
#     InlineKeyboardButton("⬇️ Ozish", callback_data="goal_cut"),
#     InlineKeyboardButton("↔️ Formani ushlash", callback_data="goal_maintain"),
#     InlineKeyboardButton("⬆️ Vazn olish", callback_data="goal_bulk"),
# ))

# ------------- HELPERS -------------

def calculate_bmr(height_cm: float, weight_kg: float, age: int, gender: str) -> float:
    """Mifflin–St Jeor"""
    if gender == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

def apply_goal_calories(tdee: float, goal: str) -> float:
    """goal_cut: -15%, goal_bulk: +15%, maintain: 0%"""
    if goal == "goal_cut":
        return tdee * 0.85
    if goal == "goal_bulk":
        return tdee * 1.15
    return tdee

@dataclass
class MacroSplit:
    protein_pct: Tuple[float, float]  # foiz (min, max yoki (x,x))
    fat_pct: Tuple[float, float]
    carb_pct: Tuple[float, float]

def get_macro_split(goal: str) -> MacroSplit:
    """
    Siz bergan proporsiyalar:
    - Ozish: 40% oqsil, 30% yog', 30% uglevod
    - Vazn olish: 30% oqsil, 20% yog', 50% uglevod
    - Formani ushlash: 30–40% oqsil, 25–30% yog', 30–40% uglevod
    """
    if goal == "goal_cut":
        return MacroSplit((40, 40), (30, 30), (30, 30))
    if goal == "goal_bulk":
        return MacroSplit((30, 30), (20, 20), (50, 50))
    # maintain: diapazon
    return MacroSplit((30, 40), (25, 30), (30, 40))

def kcal_to_grams(kcal: float, macro_pct: Tuple[float, float]) -> Tuple[float, float]:
    """
    kcal -> gramm diapazonini qaytaradi. Protein & Carb: 4 kcal/g, Fat: 9 kcal/g
    Bu funksiya universal emas, shuning uchun fat uchun alohida ishlatamiz.
    """
    p_min, p_max = macro_pct
    return (kcal * p_min / 100 / 4, kcal * p_max / 100 / 4)

def kcal_to_grams_fat(kcal: float, macro_pct: Tuple[float, float]) -> Tuple[float, float]:
    f_min, f_max = macro_pct
    return (kcal * f_min / 100 / 9, kcal * f_max / 100 / 9)

def pretty_range_or_value(unit: str, rng: Tuple[float, float]) -> str:
    a, b = rng
    if abs(a - b) < 1e-6:
        return f"{a:.0f} {unit}"
    return f"{a:.0f}–{b:.0f} {unit}"

def round_range(rng: Tuple[float, float], ndigits: int = 0) -> Tuple[float, float]:
    return (round(rng[0], ndigits), round(rng[1], ndigits))

# ------------- HANDLERS -------------

@dp.message_handler(commands=["start"], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    chat_id = message.chat.id
    start_note_file_id = "DQACAgIAAxkBAAMyaPn3S4nvf64btvwQcGIuIRq-UmMAAh6HAAINY7BLhMOC5m3sxYQ2BA"

    try:
        await bot.send_video_note(
            chat_id=chat_id,
            video_note=start_note_file_id,
        )

    except Exception as e:
        print(f"Dumaloq videoni yuborishda xatolik yuz berdi: {e}")
    await message.answer(
        "🏋Shoxrux Adxamovning botiga xush kelibsiz!\n\n"
        "Men odamlarga chiroyli va sog’lom tana qurishda yordam beraman.\n"
        "Bu yerda siz ovqatlanish, <b>KBJU</b> va <b>Trenirovka</b> dasturini o‘zingizga mos tarzda olasiz.\n\n"
        "<b><i>👇 Hoziroq boshlang.</i></b>",
        reply_markup=main_kb
    )

@dp.callback_query_handler(lambda c: c.data == "calories")
async def cb_calories(callback_query: types.CallbackQuery, state: FSMContext):
    await CaloriesStates.waiting_height.set()
    await state.update_data(tdee=None)  # keyinchalik to'ldiramiz
    await callback_query.message.answer("📏 Bo'yingizni kiriting (sm):")
    await callback_query.answer()

@dp.message_handler(state=CaloriesStates.waiting_height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        h = float(message.text)
        if not (80 <= h <= 250):
            raise ValueError
    except Exception:
        return await message.answer("Bo'yingizni to‘g‘ri kiriting (masalan, 175).")
    await state.update_data(height=h)
    await CaloriesStates.waiting_weight.set()
    await message.answer("⚖️ Vazningizni kiriting (kg):")

@dp.message_handler(state=CaloriesStates.waiting_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        w = float(message.text)
        if not (20 <= w <= 400):
            raise ValueError
    except Exception:
        return await message.answer("Vaznni to‘g‘ri kiriting (masalan, 70.5).")
    await state.update_data(weight=w)
    await CaloriesStates.waiting_age.set()
    await message.answer("🎂 Yoshingizni kiriting (yil):")

@dp.message_handler(state=CaloriesStates.waiting_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if not (10 <= age <= 100):
            raise ValueError
    except Exception:
        return await message.answer("Yoshni to‘g‘ri kiriting (masalan, 28).")
    await state.update_data(age=age)
    await CaloriesStates.waiting_gender.set()
    await message.answer("👤 Jinsingizni tanlang:", reply_markup=gender_kb)

@dp.callback_query_handler(lambda c: c.data.startswith("gender_"), state=CaloriesStates.waiting_gender)
async def process_gender(callback_query: types.CallbackQuery, state: FSMContext):
    gender = "male" if callback_query.data == "gender_male" else "female"
    await state.update_data(gender=gender)
    await CaloriesStates.waiting_activity.set()
    txt = (
"""
<b>Faollik darajalari:</b>

<b>1.2</b> — <i>Juda past faollik</i>  
(ofisda o‘tirib ishlash, jismoniy faollik deyarli yo‘q)

<b>1.375</b> — <i>Yengil faollik</i>  
(Haftasiga 1–3 marta yengil mashg‘ulotlar)

<b>1.55</b> — <i>O‘rtacha faollik</i>  
(Haftasiga 3–5 marta muntazam mashg‘ulotlar)

<b>1.725</b> — <i>Yuqori faollik</i>  
(Haftasiga 6–7 marta og‘ir yoki kuchli jismoniy mashg‘ulotlar)

<b>1.9</b> — <i>Juda yuqori faollik</i>  
(Professional sportchilar)
"""
    )
    await callback_query.message.answer(txt, reply_markup=activity_kb)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data in ACTIVITY_LEVELS.keys(), state=CaloriesStates.waiting_activity)
async def process_activity(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    activity_factor = ACTIVITY_LEVELS[callback_query.data][1]

    # BMR -> TDEE
    bmr = calculate_bmr(
        height_cm=data["height"],
        weight_kg=data["weight"],
        age=data["age"],
        gender=data["gender"]
    )
    tdee = bmr * activity_factor
    await state.update_data(tdee=tdee)

    await callback_query.message.answer(
        f"✅ <b>TDEE (faoliyat hisobga olingan): {round(tdee):,} kcal</b>\n\n"
        "Endi maqsadni tanlang:",
        reply_markup=goal_kb
    )
    await CaloriesStates.waiting_goal.set()
    await callback_query.answer()

REMINDER_VIDEO_ID = "DQACAgIAAxkBAAM4aPn5bkWllqkRlSN8Sl-oNRaFgUoAAimHAAINY7BL94xewyKge0o2BA"


async def send_reminder_video(bot: Bot, chat_id: int, file_id: str):
    """Belgilangan chat_id ga dumaloq videoni yuboruvchi funksiya."""
    try:
        await bot.send_video_note(
            chat_id=chat_id,
            video_note=file_id
        )
    except Exception as e:
        print(f"[{datetime.now()}] Chat {chat_id} ga video yuborishda xatolik: {e}")

@dp.callback_query_handler(lambda c: c.data in ("goal_cut", "goal_maintain", "goal_bulk"), state=CaloriesStates.waiting_goal)
async def process_goal(callback_query: types.CallbackQuery, state: FSMContext):
    goal = callback_query.data
    data = await state.get_data()
    tdee = float(data.get("tdee", 0.0))

    if tdee <= 0:
        await callback_query.message.answer("Xatolik: TDEE topilmadi. /start dan qayta urinib ko‘ring.")
        await state.finish()
        return

    target_kcal = apply_goal_calories(tdee, goal)
    split = get_macro_split(goal)

    # Grammlarga o'tkazish
    # protein & carb: 4 kcal/g, fat: 9 kcal/g
    p_g = round_range(kcal_to_grams(target_kcal, split.protein_pct))
    f_g = round_range(kcal_to_grams_fat(target_kcal, split.fat_pct))
    c_g = round_range(kcal_to_grams(target_kcal, split.carb_pct))

    # Ko‘rinishni chiroyli qilish
    goal_name = {"goal_cut": "⬇️ Ozish", "goal_maintain": "↔️ Formani ushlash", "goal_bulk": "⬆️ Vazn olish"}[goal]

    # Foizlarni matnga
    def pct_txt(p: Tuple[float, float]) -> str:
        a, b = p
        return f"{a:.0f}%" if abs(a-b) < 1e-6 else f"{a:.0f}–{b:.0f}%"

    msg = (
        f"{goal_name} uchun KBJU hisob kitobi:\n\n"
        f"🔥 <b>Kunlik kaloriya:</b> {round(target_kcal):,} kcal\n"
        f"🍗 Oqsil: → {pretty_range_or_value('g', p_g)}\n"
        f"🥑 Yog' → {pretty_range_or_value('g', f_g)}\n"
        f"🍚 Uglevod → {pretty_range_or_value('g', c_g)}\n\n"

    )
    user_obj, _ = await sync_to_async(User.objects.get_or_create)(
        telegram_id=callback_query.from_user.id,
        defaults={
            "username": callback_query.from_user.username,
            "first_name": callback_query.from_user.first_name,
        }
    )

    await sync_to_async(CalorieRecord.objects.create)(
        user=user_obj,
        height=data["height"],
        weight=data["weight"],
        age=data["age"],
        gender=data["gender"],
        activity=ACTIVITY_LEVELS[callback_query.data][1]
        if callback_query.data in ACTIVITY_LEVELS
        else 1.0,
        goal=goal,
        tdee=tdee,
        protein=p_g[0],
        fat=f_g[0],
        carb=c_g[0],
    )

    await callback_query.message.answer(msg, reply_markup=caloriya_cb)
    await state.finish()
    await callback_query.answer()

    # 2. 5 daqiqadan so'ng VideoNote yuborishni rejalashtirish

    # Eslatmani yuborish vaqti (hozirgi vaqt + 5 daqiqa)
    run_date = datetime.now() + timedelta(seconds=10)
    chat_id = callback_query.message.chat.id

    # Scheduler orqali vazifani rejalashtirish
    scheduler.add_job(
        send_reminder_video,  # Chaqliriladigan funksiya
        'date',  # Qaysi usulda rejalashtirish (sana/vaqt bo'yicha)
        run_date=run_date,  # Belgilangan vaqt
        args=[bot, chat_id, REMINDER_VIDEO_ID]  # Funksiyaga uzatiladigan argumentlar
    )

    print(f"[{datetime.now()}] Chat {chat_id} uchun video eslatma {run_date} ga rejalashtirildi.")

# (Ixtiyoriy) Workouts / nutrition tugmalari hozircha stub:
@dp.callback_query_handler(lambda c: c.data == "workout")
async def cb_workout(callback_query: types.CallbackQuery):
    await callback_query.message.answer("💪 Workout bo‘limi tez orada qo‘shiladi.")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "nutrition")
async def cb_nutrition(callback_query: types.CallbackQuery):
    await callback_query.message.answer("🍽️ Ovqat menyusi bo‘limi tez orada qo‘shiladi.")
    await callback_query.answer()




# ------------- RUN -------------
if __name__ == '__main__':
    executor.start_polling(
        dp,
        on_startup=on_startup_notify, # <<--- Shu yerga qo'shiladi
        skip_updates=True
    )