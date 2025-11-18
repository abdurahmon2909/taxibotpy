import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties

import gspread
from oauth2client.service_account import ServiceAccountCredentials


# =========================================================
# 🔧 SETTINGS
# =========================================================

BOT_TOKEN = "8531632256:AAEc9P5iTFwA9a13YI0zv9-0DQayBQEOLLk"
ADMIN_CHAT_ID = 1563018448

CHANNEL_ID = -1002836724965
CHANNEL_USERNAME = "Beshariq_Toshkent_taxiuz2"
CHANNEL_LINK = "https://t.me/Beshariq_Toshkent_taxiuz2"

SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_ID = "1XNXM8b1FJ-uGcsCgEVQFzVWE6S8xS9zFjBGySY7Lfas"
WORKSHEET_NAME = "Orders"


# =========================================================
# 📌 GOOGLE SHEETS
# =========================================================

import json
import os

def get_sheet():
    try:
        creds_path = os.getenv("GOOGLE_CREDS_FILE")
        if not creds_path:
            raise Exception("GOOGLE_CREDS_FILE not found")

        with open(creds_path, "r") as f:
            creds_dict = json.load(f)

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive",
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID)

        try:
            return sheet.worksheet(WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sheet.add_worksheet(WORKSHEET_NAME, rows="2000", cols="20")
            ws.append_row([
                "Timestamp", "User ID", "Username", "Full Name",
                "Phone", "Route", "Point A", "Point B", "When"
            ])
            return ws

    except Exception as e:
        logging.error(f"Google Sheets xatosi: {e}")
        return None


# =========================================================
# 📍 DISTRICTS
# =========================================================

DISTRICTS_TOSHKENT = [
    "Bektemir",
    "Chilonzor",
    "Mirabad",
    "Mirzo-Ulug`bek",
    "Olmazor",
    "Sergeli",
    "Shayxontohur",
    "Uchtepa",
    "Yakkasaroy",
    "Yangihayot",
    "Yashnobod",
    "Yunusobod"
]

DISTRICTS_BESHARIQ = [
    "Beshariq markazi", "Zarqaynar", "Yakkatut",
    "Shoberdi", "Qizilbayroq", "Uvada", "Kulol","Tovul"
]


# =========================================================
# 🧠 FSM STATES
# =========================================================

class TaxiForm(StatesGroup):
    waiting_phone = State()
    waiting_route = State()
    waiting_point_a = State()
    waiting_point_b = State()
    waiting_when = State()
    waiting_datetime = State()


# =========================================================
# 📌 KEYBOARDS
# =========================================================

def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqam ulashish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def check_sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📣 Kanalga obuna bo'lish", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")]
    ])


def route_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="BESHARIQdan ➝ TOSHKENTga", callback_data="route_besh_tosh")],
        [InlineKeyboardButton(text="TOSHKENTdan ➝ BESHARIQga", callback_data="route_tosh_besh")],
    ])


def district_keyboard(items, prefix):
    keyboard = []
    row = []
    for i, d in enumerate(items, 1):
        row.append(InlineKeyboardButton(text=d, callback_data=f"{prefix}{d}"))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def when_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚖 Hoziroq", callback_data="when_now")],
        [InlineKeyboardButton(text="🗓 Sana va vaqtni kiritish", callback_data="when_later")]
    ])


def cancel_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order")]
    ])


def restart_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚕 Yana taksi kerakmi?", callback_data="restart_bot")]
    ])


# =========================================================
# 🔒 CHECK SUBSCRIPTION
# =========================================================

async def is_subscribed(user_id: int, bot: Bot) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False


# =========================================================
# 🤖 BOT INIT
# =========================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


# =========================================================
# 🟢 START
# =========================================================

@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()

    if not await is_subscribed(message.from_user.id, bot):
        await message.answer(
            f"👋 Assalomu alaykum, hurmatli {message.from_user.full_name}!\n\n"
            f"Safar uchun chegirmalar, bonuslar🎁 va yangiliklardan xabardor bo`lish uchun bizga qo`shiling:\n\n"
            
            f"Va tekshirish tugmasini bosing 👇",
            reply_markup=check_sub_keyboard()
        )
        return

    await message.answer("📱 Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
    await state.set_state(TaxiForm.waiting_phone)


@dp.callback_query(F.data == "restart_bot")
async def restart_bot(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await start_cmd(call.message, state)


@dp.callback_query(F.data == "check_sub")
async def check_subscription(call: CallbackQuery, state: FSMContext):
    if await is_subscribed(call.from_user.id, bot):
        await call.message.edit_text("✅ Obuna tasdiqlandi!")
        await call.message.answer("📱 Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
        await state.set_state(TaxiForm.waiting_phone)
    else:
        await call.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)


# =========================================================
# PHONE INPUT
# =========================================================

@dp.message(F.contact, TaxiForm.waiting_phone)
async def phone_input_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number

    await state.update_data(
        phone=phone,
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name
    )

    await message.answer(f"📞 Raqamingiz qabul qilindi: {phone}", reply_markup=types.ReplyKeyboardRemove())
    sent = await message.answer("Yo'nalishni tanlang:", reply_markup=route_keyboard())
    await state.update_data(last_msg_id=sent.message_id)
    await state.set_state(TaxiForm.waiting_route)


@dp.message(TaxiForm.waiting_phone)
async def phone_input_text(message: Message, state: FSMContext):
    phone = message.text.strip()

    if not phone or len(phone) < 5:
        await message.answer("❌ Noto‘g‘ri raqam! Yana urinib ko‘ring.")
        return

    await state.update_data(
        phone=phone,
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name
    )

    await message.answer(f"📞 Raqam qabul qilindi: {phone}", reply_markup=types.ReplyKeyboardRemove())
    sent = await message.answer("Yo'nalishni tanlang:", reply_markup=route_keyboard())
    await state.update_data(last_msg_id=sent.message_id)
    await state.set_state(TaxiForm.waiting_route)


# =========================================================
# ROUTE
# =========================================================

@dp.callback_query(F.data.startswith("route_"), TaxiForm.waiting_route)
async def route_selected(call: CallbackQuery, state: FSMContext):
    if call.data == "route_besh_tosh":
        route = "Beshariq ➝ Toshkent"
        from_d = DISTRICTS_BESHARIQ
        to_d = DISTRICTS_TOSHKENT
    else:
        route = "Toshkent ➝ Beshariq"
        from_d = DISTRICTS_TOSHKENT
        to_d = DISTRICTS_BESHARIQ

    await state.update_data(route=route, districts_from=from_d, districts_to=to_d)

    await call.message.edit_text("Qayerdan ketasiz?", reply_markup=district_keyboard(from_d, "A_"))
    await state.set_state(TaxiForm.waiting_point_a)


# =========================================================
# POINT A
# =========================================================

@dp.callback_query(F.data.startswith("A_"), TaxiForm.waiting_point_a)
async def point_a_selected(call: CallbackQuery, state: FSMContext):
    point_a = call.data[2:]
    await state.update_data(point_a=point_a)

    data = await state.get_data()
    await call.message.edit_text("Qayerga borasiz?", reply_markup=district_keyboard(data["districts_to"], "B_"))
    await state.set_state(TaxiForm.waiting_point_b)


# =========================================================
# POINT B
# =========================================================

@dp.callback_query(F.data.startswith("B_"), TaxiForm.waiting_point_b)
async def point_b_selected(call: CallbackQuery, state: FSMContext):
    await state.update_data(point_b=call.data[2:])
    await call.message.edit_text("Qachon ketmoqchisiz?", reply_markup=when_keyboard())
    await state.set_state(TaxiForm.waiting_when)


# =========================================================
# WHEN
# =========================================================

@dp.callback_query(F.data == "when_now", TaxiForm.waiting_when)
async def when_now(call: CallbackQuery, state: FSMContext):
    await state.update_data(when="Hoziroq")
    await finish_order(call.message, state)


@dp.callback_query(F.data == "when_later", TaxiForm.waiting_when)
async def when_later(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "Sana va vaqtni kiriting:\nMasalan: <b>20.11.2025, 21:30</b> yoki <b>'Ertaga ertalab'</b>",
        reply_markup=cancel_inline_keyboard()
    )
    await state.set_state(TaxiForm.waiting_datetime)


@dp.callback_query(F.data == "cancel_order")
async def cancel_order(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Buyurtma bekor qilindi.")


# =========================================================
# DATETIME INPUT
# =========================================================

@dp.message(TaxiForm.waiting_datetime)
async def datetime_input(message: Message, state: FSMContext):
    when_text = message.text.strip()
    await state.update_data(when=when_text)
    await finish_order(message, state)


# =========================================================
# SAVE ORDER
# =========================================================

async def finish_order(message: Message, state: FSMContext):
    data = await state.get_data()
    sheet = get_sheet()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save to Sheet
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

    admin_text = (
    "🚖 <b>Yangi buyurtma!</b>\n\n"
    f"🕒 {timestamp}\n"
    f"👤 <b>Ism:</b> {data['full_name']}\n"
    f"🔗 <b>Username:</b> @{data['username'] if data['username'] else '-'}\n"
    f"📞 <b>Telefon:</b> {data['phone']}\n\n"
    f"🛣 <b>Yo'nalish:</b> {data['route']}\n"
    f"📍 <b>Qayerdan:</b> {data['point_a']}\n"
    f"📍 <b>Qayerga:</b> {data['point_b']}\n"
    f"🗓 <b>Ketish vaqti:</b> {data['when']}"
    )


    await bot.send_message(ADMIN_CHAT_ID, admin_text)

    final_text = (
        "✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"🛣 <b>Yo'nalish:</b> {data['route']}\n"
        f"📍 <b>A:</b> {data['point_a']}\n"
        f"📍 <b>B:</b> {data['point_b']}\n"
        f"🗓 <b>{data['when']}</b>\n"
        f"📞 <b>{data['phone']}</b>\n\n"
        "Tez orada siz bilan bog'lanamiz!"
    )

    await message.answer(final_text, reply_markup=restart_keyboard())
    await state.clear()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    logging.info("Bot ishga tushdi...")
    dp.run_polling(bot)



