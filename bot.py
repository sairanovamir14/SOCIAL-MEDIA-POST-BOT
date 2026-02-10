import os
from dotenv import load_dotenv

from db import SessionLocal
from models import User


import asyncio
import requests
import openai

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")
META_TOKEN = os.getenv("META_TOKEN")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

CHANNEL = os.getenv("CHANNEL")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
IG_USER_ID = os.getenv("IG_USER_ID")

openai.api_key = OPENAI_KEY


# ================================
# BOT INIT
# ================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================================
#  TOKEN VERIFICATION
# ================================

def get_user_by_token(token):
    db = SessionLocal()
    user = db.query(User).filter(User.api_token == token).first()
    db.close()
    return user

def get_user_by_tg(tg_id):
    db = SessionLocal()
    user = db.query(User).filter(User.tg_id == tg_id).first()
    db.close()
    return user

# ================================
# STATES
# ================================

class PostState(StatesGroup):
    topic = State()
    choose_image = State()
    photo = State()
    link = State()
    gen_image_prompt = State()
    language = State()
    preview = State()
    edit_manual = State()
    edit_ai = State()
    choose_platform = State()


# ================================
# KEYBOARDS
# ================================

def image_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Загрузить фото", callback_data="upload")],
        [InlineKeyboardButton(text="🔗 Вставить ссылку", callback_data="link")],
        [InlineKeyboardButton(text="🎨 Сгенерировать изображение", callback_data="gen")]
    ])

def language_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="ru")],
        [InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="kz")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="en")]
    ])

def post_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать вручную", callback_data="edit_manual")],
        [InlineKeyboardButton(text="🤖 Изменить через ИИ", callback_data="edit_ai")],
        [InlineKeyboardButton(text="🚀 Опубликовать", callback_data="publish")]
    ])

def platform_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Telegram", callback_data="tg")],
        [InlineKeyboardButton(text="📸 Instagram", callback_data="ig")],
        [InlineKeyboardButton(text="📘 Facebook", callback_data="fb")],
        [InlineKeyboardButton(text="🌍 Везде", callback_data="all")]
    ])

def restart_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Начать заново", callback_data="restart")]
    ])


# ================================
# AI
# ================================

from openai import OpenAI

client = OpenAI(api_key=OPENAI_KEY)

def ask_gpt(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=900
        )
        return response.choices[0].message.content
    except Exception as e:
        print("GPT ERROR:", e)
        return "⚠️ Ошибка генерации."


def generate_image(prompt):
    result = openai.Image.create(
        model="dall-e-3",
        prompt=f"High quality social media image, vertical composition, {prompt}",
        size="1024x1792"
    )
    return result["data"][0]["url"]

GENERATOR_PROMPT = """
Ты профессиональный SMM-копирайтер.
Пиши на {language}.
Создай пост из 5–7 предложений.
Стиль живой и понятный.
Добавь 3–6 релевантных хештегов.
Тема:
"""

EDITOR_PROMPT = """
Ты редактор текста.
Если просят переписать — перепиши полностью.
Если просят изменить часть — измени только её.
Сохраняй язык.
Верни только готовый текст.

ТЕКСТ:
{OLD}

ИНСТРУКЦИЯ:
{USER}
"""

def generate_post(topic, lang):
    lang_map = {
        "ru": "русском языке",
        "kz": "казахском языке",
        "en": "английском языке"
    }
    return ask_gpt(GENERATOR_PROMPT.format(language=lang_map[lang]) + topic)

def edit_post(old, instruction):
    return ask_gpt(
        EDITOR_PROMPT.replace("{OLD}", old).replace("{USER}", instruction)
    )


# ================================
# IMGBB
# ================================

def upload_imgbb(url):
    r = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": url}
    )
    return r.json()["data"]["display_url"]


# ================================
# META
# ================================

async def post_facebook(photo_url, caption):
    requests.post(
        f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
        data={"url": photo_url, "caption": caption, "access_token": META_TOKEN}
    )

async def post_instagram(photo_url, caption):
    r = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={"image_url": photo_url, "caption": caption, "access_token": META_TOKEN}
    )
    cid = r.json().get("id")
    if cid:
        requests.post(
            f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
            data={"creation_id": cid, "access_token": META_TOKEN}
        )


# ================================
# START
# ================================

@dp.message(Command("start"))
async def start(msg: types.Message):
    user = get_user_by_tg(msg.from_user.id)

    if user:
        await msg.answer("✅ Вы уже авторизованы. Напишите /menu")
        return

    await msg.answer("Введите токен с сайта:")

@dp.message(Command("menu"))
async def menu(msg: types.Message, state: FSMContext):
    user = get_user_by_tg(msg.from_user.id)

    if not user:
        await msg.answer("🔐 Сначала введите токен через /start")
        return

    await msg.answer("✍️ Напиши тему поста:")
    await state.set_state(PostState.topic)
    
@dp.message(Command("unlink"))
async def unlink(msg: types.Message):
    db = SessionLocal()
    user = db.query(User).filter(User.tg_id == msg.from_user.id).first()

    if not user:
        db.close()
        await msg.answer("Вы не привязаны.")
        return

    user.tg_id = None
    db.commit()
    db.close()

    await msg.answer("🔓 Аккаунт отвязан. Теперь введите токен заново через /start")

# ================================
# RESTART BUTTON
# ================================

@dp.callback_query(lambda c: c.data == "restart")
async def restart(call, state: FSMContext):
    await state.clear()
    await call.message.answer("✍️ Напиши тему поста:")
    await state.set_state(PostState.topic)


# ================================
# TOPIC
# ================================

@dp.message(PostState.topic)
async def topic(msg, state):
    await state.update_data(topic=msg.text)
    await msg.answer("🖼 Как добавить изображение?", reply_markup=image_kb())
    await state.set_state(PostState.choose_image)


# ================================
# IMAGE TYPE
# ================================

@dp.callback_query(PostState.choose_image)
async def choose_image(call, state):
    if call.data == "upload":
        await call.message.answer("📸 Отправь фото:")
        await state.set_state(PostState.photo)

    elif call.data == "link":
        await call.message.answer("🔗 Вставь ссылку:")
        await state.set_state(PostState.link)

    elif call.data == "gen":
        await call.message.answer("🎨 Опиши изображение:")
        await state.set_state(PostState.gen_image_prompt)


# ================================
# PHOTO
# ================================

@dp.message(PostState.photo)
async def photo(msg, state):
    file_id = msg.photo[-1].file_id
    file = await bot.get_file(file_id)
    tg_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    url = upload_imgbb(tg_url)

    await state.update_data(photo_url=url)
    await msg.answer("🌍 Выбери язык:", reply_markup=language_kb())
    await state.set_state(PostState.language)


# ================================
# LINK
# ================================

@dp.message(PostState.link)
async def link(msg, state):
    url = upload_imgbb(msg.text)
    await state.update_data(photo_url=url)
    await msg.answer("🌍 Выбери язык:", reply_markup=language_kb())
    await state.set_state(PostState.language)


# ================================
# GENERATE IMAGE
# ================================

@dp.message(PostState.gen_image_prompt)
async def gen_image(msg, state):
    await msg.answer("🎨 Генерирую изображение...")

    img_url = generate_image(msg.text)
    hosted = upload_imgbb(img_url)

    await state.update_data(photo_url=hosted)
    await msg.answer("🌍 Выбери язык:", reply_markup=language_kb())
    await state.set_state(PostState.language)


# ================================
# LANGUAGE
# ================================

@dp.callback_query(PostState.language)
async def set_lang(call, state):
    await state.update_data(language=call.data)
    await create_post(call.message, state)


# ================================
# CREATE POST
# ================================

async def create_post(msg, state):
    data = await state.get_data()
    text = generate_post(data["topic"], data["language"])

    await state.update_data(text=text)

    await msg.answer_photo(
        data["photo_url"],
        caption=text,
        reply_markup=post_kb()
    )

    await state.set_state(PostState.preview)


# ================================
# EDIT MANUAL
# ================================

@dp.callback_query(PostState.preview, lambda c: c.data == "edit_manual")
async def manual(call, state):
    await call.message.answer("✏️ Отправь новый текст:")
    await state.set_state(PostState.edit_manual)

@dp.message(PostState.edit_manual)
async def save_manual(msg, state):
    await state.update_data(text=msg.text)
    await create_preview(msg, state)


# ================================
# EDIT AI
# ================================

@dp.callback_query(PostState.preview, lambda c: c.data == "edit_ai")
async def ai_edit(call, state):
    await call.message.answer("🤖 Что изменить?")
    await state.set_state(PostState.edit_ai)

@dp.message(PostState.edit_ai)
async def save_ai(msg, state):
    data = await state.get_data()
    new = edit_post(data["text"], msg.text)

    await state.update_data(text=new)
    await create_preview(msg, state)


async def create_preview(msg, state):
    data = await state.get_data()
    await msg.answer_photo(
        data["photo_url"],
        caption=data["text"],
        reply_markup=post_kb()
    )
    await state.set_state(PostState.preview)


# ================================
# PUBLISH
# ================================

@dp.callback_query(PostState.preview, lambda c: c.data == "publish")
async def publish(call, state):
    await call.message.answer("🚀 Куда публиковать?", reply_markup=platform_kb())
    await state.set_state(PostState.choose_platform)

@dp.callback_query(PostState.choose_platform)
async def platform(call, state):
    data = await state.get_data()

    if call.data in ["tg", "all"]:
        await bot.send_photo(CHANNEL, data["photo_url"], caption=data["text"])

    if call.data in ["ig", "all"]:
        await post_instagram(data["photo_url"], data["text"])

    if call.data in ["fb", "all"]:
        await post_facebook(data["photo_url"], data["text"])

    await call.message.answer(
        "✅ Пост опубликован!",
        reply_markup=restart_kb()
    )

@dp.message()
async def receive_token(msg: types.Message):
    if msg.text.startswith("/"):
        return

    token = msg.text.strip()

    db = SessionLocal()
    user = db.query(User).filter(User.api_token == token).first()

    if not user:
        db.close()
        await msg.answer("❌ Неверный токен")
        return

    if user.tg_id is not None and user.tg_id != msg.from_user.id:
        db.close()
        await msg.answer("❌ Этот токен уже используется")
        return

    user.tg_id = msg.from_user.id
    db.commit()
    db.close()

    await msg.answer("✅ Аккаунт привязан! Напишите /menu")

    


# ================================
# RUN
# ================================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
