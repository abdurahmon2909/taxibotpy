import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from fastapi import FastAPI, Request
import uvicorn

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------

BOT_TOKEN = "8531632256:AAEc9P5iTFwA9a13YI0zv9-0DQayBQEOLLk"
ADMIN_CHAT_ID = 1563018448

WEBHOOK_HOST = "https://taxibotpy.up.railway.app"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_ID = "1XNXM8b1FJ-uGcsCgEVQFzVWE6S8xS9zFjBGySY7Lfas"
WORKSHEET_NAME = "Orders"

# -----------------------------------------------------------

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
app = FastAPI()


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
# FSM
# -----------------------------------------------------------

class TaxiForm(StatesGroup):
    waiting_phone = State()
    waiting_route = State()
    waiting_point_a = State()
    waiting_point_b = State()
    waiting_when = State()
    waiting_datetime = State()
    message_id = State()


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
    kb.button(text="🗓 Sana va soat", callback_data="when_later")
    kb.adjust(1)
    return kb.as_markup()


# -----------------------------------------------------------
# START
# -----------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    full = message.from_user.full_name
    hello_text = f"👋 Assalomu alaykum, <b>{full}</b>!\n" \
                 f"Quyida raqamingizni yuboring:"

    sent = await message.answer(hello_text, reply_markup=phone_keyboard())

    # сохраняем ID сообщения, чтобы мы могли обновлять СУЩЕСТВУЮЩЕЕ, а не отправлять новые
    await state.update_data(message_id=sent.message_id)

    await state.set_state(TaxiForm.waiting_phone)


# -----------------------------------------------------------
# UPDATE MESSAGE FUNCTION
# -----------------------------------------------------------

async def edit(state, chat_id, text, reply_markup=None):
    data = await state.get_data()
    msg_id = data.get("message_id")

    await bot.edit_message_text(
        text, chat_id, msg_id, reply_markup=reply_markup
    )


# -----------------------------------------------------------
# PHONE
# -----------------------------------------------------------

@dp.message(F.contact, TaxiForm.waiting_phone)
async def get_phone(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)

    await edit(state, message.chat.id,
               f"📞 Rahmat, raqamingiz qabul qilindi: <b>{phone}</b>\n\nEndi yo`nalishni tanlang:",
               reply_markup=route_keyboard())

    await state.set_state(TaxiForm.waiting_route)


@dp.message(TaxiForm.waiting_phone)
async def get_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)

    await edit(state, message.chat.id,
               f"📞 Rahmat, raqamingiz qabul qilindi: <b>{phone}</b>\n\nEndi yo‘nalishni tanlang:",
               reply_markup=route_keyboard())

    await state.set_state(TaxiForm.waiting_route)


# -----------------------------------------------------------
# ROUTE
# -----------------------------------------------------------

@dp.callback_query(F.data.startswith("route_"), TaxiForm.waiting_route)
async def choose_route(call: CallbackQuery, state: FSMContext):
    route = "Beshariq ➝ Toshkent" if call.data == "route_besh_tosh" else "Toshkent ➝ Beshariq"

    districts_from = DISTRICTS_BESHARIQ if "besh" in call.data else DISTRICTS_TOSHKENT
    districts_to = DISTRICTS_TOSHKENT if districts_from == DISTRICTS_BESHARIQ else DISTRICTS_BESHARIQ

    await state.update_data(route=route, districts_from=districts_from, districts_to=districts_to)

    await edit(state, call.message.chat.id,
               "📍 Qayerdan ketasiz?",
               reply_markup=district_keyboard(districts_from, "A_"))

    await state.set_state(TaxiForm.waiting_point_a)


# -----------------------------------------------------------
# POINT A
# -----------------------------------------------------------

@dp.callback_query(F.data.startswith("A_"), TaxiForm.waiting_point_a)
async def choose_point_a(call: CallbackQuery, state: FSMContext):
    point_a = call.data[2:]
    await state.update_data(point_a=point_a)

    data = await state.get_data()
    districts_to = data["districts_to"]

    await edit(state, call.message.chat.id,
               "📍 Qayerga borasiz?",
               reply_markup=district_keyboard(districts_to, "B_"))

    await state.set_state(TaxiForm.waiting_point_b)


# -----------------------------------------------------------
# POINT B
# -----------------------------------------------------------

@dp.callback_query(F.data.startswith("B_"), TaxiForm.waiting_point_b)
async def choose_point_b(call: CallbackQuery, state: FSMContext):
    point_b = call.data[2:]
    await state.update_data(point_b=point_b)

    await edit(state, call.message.chat.id,
               "⏱ Qachon ketmoqchisiz?",
               reply_markup=when_keyboard())

    await state.set_state(TaxiForm.waiting_when)


# -----------------------------------------------------------
# WHEN
# -----------------------------------------------------------

@dp.callback_query(F.data == "when_now", TaxiForm.waiting_when)
async def when_now(call: CallbackQuery, state: FSMContext):
    await state.update_data(when="Hoziroq")
    await finish_order(call.message.chat.id, state)


@dp.callback_query(F.data == "when_later", TaxiForm.waiting_when)
async def when_later(call: CallbackQuery, state: FSMContext):
    await edit(state, call.message.chat.id, "Sanani va vaqtni kiriting:")
    await state.set_state(TaxiForm.waiting_datetime)


@dp.message(TaxiForm.waiting_datetime)
async def get_datetime(message: Message, state: FSMContext):
    await state.update_data(when=message.text)
    await finish_order(message.chat.id, state)


# -----------------------------------------------------------
# FINISH ORDER
# -----------------------------------------------------------

async def finish_order(chat_id, state):
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

    # отправка админу
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

    # клиенту
    await edit(state, chat_id,
               "✅ Buyurtmangiz qabul qilindi! \nSiz bilan tez orada bog`lanamiz!")

    await state.clear()


# -----------------------------------------------------------
# WEBHOOKS
# -----------------------------------------------------------

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    update = await request.json()
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)


@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()


# -----------------------------------------------------------
# RAILWAY RUN
# -----------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

