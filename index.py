import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------

BOT_TOKEN = "8531632256:AAEc9P5iTFwA9a13YI0zv9-0DQayBQEOLLk"
ADMIN_CHAT_ID = 1563018448

SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_ID = "1XNXM8b1FJ-uGcsCgEVQFzVWE6S8xS9zFjBGySY7Lfas"
WORKSHEET_NAME = "Orders"

# -----------------------------------------------------------
# GOOGLE SHEETS
# -----------------------------------------------------------

def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        SERVICE_ACCOUNT_FILE, scope
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except:
        worksheet = spreadsheet.add_worksheet(WORKSHEET_NAME, rows="1000", cols="20")
        worksheet.append_row([
            "Timestamp", "User ID", "Username", "Full Name",
            "Phone", "Route", "Point A", "Point B", "When"
        ])
    return worksheet


# -----------------------------------------------------------
# DISTRICTS
# -----------------------------------------------------------

DISTRICTS_TOSHKENT = [
    "Chilonzor", "Sergeli", "Yunusobod", "Yakkasaroy",
    "Mirzo Ulug‘bek", "Olmazor", "Shayxontohur", "Yashnobod"
]

DISTRICTS_BESHARIQ = [
    "Beshariq markazi", "Zarqaynar", "Yakkatut", "Shoberdi", "Qizilbayroq"
]


# -----------------------------------------------------------
# FSM STATES
# -----------------------------------------------------------

class TaxiForm(StatesGroup):
    waiting_phone = State()
    waiting_route = State()
    waiting_point_a = State()
    waiting_point_b = State()
    waiting_when = State()
    waiting_datetime = State()


# -----------------------------------------------------------
# KEYBOARDS
# -----------------------------------------------------------

def phone_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📱 Raqam ulashish", request_contact=True)
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def route_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Beshariq ➝ Toshkent", callback_data="route_besh_tosh")
    kb.button(text="Toshkent ➝ Beshariq", callback_data="route_tosh_besh")
    kb.adjust(1)
    return kb.as_markup()

def district_keyboard(districts, prefix):
    kb = InlineKeyboardBuilder()
    for d in districts:
        kb.button(text=d, callback_data=f"{prefix}{d}")
    kb.adjust(2)
    return kb.as_markup()

def when_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚖 Hoziroq", callback_data="when_now")
    kb.button(text="🗓 Sana va vaqt", callback_data="when_later")
    kb.adjust(1)
    return kb.as_markup()


# -----------------------------------------------------------
# BOT + DISPATCHER
# -----------------------------------------------------------

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


# -----------------------------------------------------------
# HANDLERS
# -----------------------------------------------------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()

    await state.update_data(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or "",
    )

    name = message.from_user.full_name
    await message.answer(
        f"👋 Assalomu alaykum, <b>{name}</b>!\n\n"
        "📱 Iltimos, telefon raqamingizni yuboring:",
        reply_markup=phone_keyboard()
    )
    await state.set_state(TaxiForm.waiting_phone)


@dp.message(F.contact, TaxiForm.waiting_phone)
async def get_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)

    await message.answer(
        f"📞 Raqam qabul qilindi: <b>{phone}</b>",
        reply_markup=types.ReplyKeyboardRemove()
    )

    await message.answer("Yo‘nalishni tanlang:", reply_markup=route_keyboard())
    await state.set_state(TaxiForm.waiting_route)


@dp.message(TaxiForm.waiting_phone)
async def get_phone_text(message: Message, state: FSMContext):
    phone = message.text
    await state.update_data(phone=phone)

    await message.answer(
        f"📞 Raqam qabul qilindi: <b>{phone}</b>",
        reply_markup=types.ReplyKeyboardRemove()
    )

    await message.answer("Yo‘nalishni tanlang:", reply_markup=route_keyboard())
    await state.set_state(TaxiForm.waiting_route)


@dp.callback_query(F.data.startswith("route_"), TaxiForm.waiting_route)
async def choose_route(call: CallbackQuery, state: FSMContext):
    if call.data == "route_besh_tosh":
        route = "Beshariq ➝ Toshkent"
        districts_from = DISTRICTS_BESHARIQ
        districts_to = DISTRICTS_TOSHKENT
    else:
        route = "Toshkent ➝ Beshariq"
        districts_from = DISTRICTS_TOSHKENT
        districts_to = DISTRICTS_BESHARIQ

    await state.update_data(route=route, districts_from=districts_from, districts_to=districts_to)

    await call.message.answer("📍 Qayerdan ketasiz?", reply_markup=district_keyboard(districts_from, "A_"))
    await state.set_state(TaxiForm.waiting_point_a)


@dp.callback_query(F.data.startswith("A_"), TaxiForm.waiting_point_a)
async def choose_point_a(call: CallbackQuery, state: FSMContext):
    point_a = call.data[2:]
    await state.update_data(point_a=point_a)

    districts_to = (await state.get_data())["districts_to"]

    await call.message.answer("📍 Qayerga borasiz?", reply_markup=district_keyboard(districts_to, "B_"))
    await state.set_state(TaxiForm.waiting_point_b)


@dp.callback_query(F.data.startswith("B_"), TaxiForm.waiting_point_b)
async def choose_point_b(call: CallbackQuery, state: FSMContext):
    point_b = call.data[2:]
    await state.update_data(point_b=point_b)

    await call.message.answer("⏱ Qachon ketmoqchisiz?", reply_markup=when_keyboard())
    await state.set_state(TaxiForm.waiting_when)


@dp.callback_query(F.data == "when_now", TaxiForm.waiting_when)
async def when_now(call: CallbackQuery, state: FSMContext):
    await state.update_data(when="Hoziroq")
    await finish_order(call.message, state)


@dp.callback_query(F.data == "when_later", TaxiForm.waiting_when)
async def when_later(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Sana va vaqtni kiriting:\nMasalan: 20.11.2025 21:30")
    await state.set_state(TaxiForm.waiting_datetime)


@dp.message(TaxiForm.waiting_datetime)
async def get_datetime(message: Message, state: FSMContext):
    await state.update_data(when=message.text)
    await finish_order(message, state)


# -----------------------------------------------------------
# SAVE ORDER
# -----------------------------------------------------------

async def finish_order(message: Message, state: FSMContext):
    data = await state.get_data()

    sheet = get_sheet()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sheet.append_row([
        timestamp,
        data["user_id"],
        data["username"],
        data["full_name"],
        data["phone"],
        data["route"],
        data["point_a"],
        data["point_b"],
        data["when"]
    ])

    # ADMIN MESSAGE
    text = (
        "🚖 <b>Yangi buyurtma!</b>\n\n"
        f"🕒 {timestamp}\n"
        f"👤 User: @{data['username']}\n"
        f"📞 Tel: {data['phone']}\n"
        f"📍 {data['route']}\n"
        f"➡ A: {data['point_a']}\n"
        f"➡ B: {data['point_b']}\n"
        f"🗓 {data['when']}"
    )

    await bot.send_message(ADMIN_CHAT_ID, text)

    await message.answer("✅ Buyurtmangiz qabul qilindi!")
    await state.clear()


# -----------------------------------------------------------
# RUN BOT
# -----------------------------------------------------------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
