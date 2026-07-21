"""================================================================
  MUSIQA BOT — PYTHON 3.13 REJIMIGA MOSLASHTIRILGAN XAVFSIZ KOD
================================================================"""
import asyncio
import logging
import os
import subprocess
import uuid
import requests
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiosqlite

logging.basicConfig(level=logging.INFO)

# ============================================================
# config.py
# ============================================================
load_dotenv()

BOT_TOKEN = "8922320901:AAGtDeCizMPNVj9-eklPOOr_MnIJ-fVf2KA"
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8004582786").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "bot.db")
TEMP_DIR = "temp"
SONGS_PER_PAGE = 10

# ============================================================
# database/db.py
# ============================================================
CREATE_USERS = """CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT NULL,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP);"""

CREATE_CHANNELS = """CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    title TEXT,
    url TEXT);"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute(CREATE_USERS)
        await db_conn.execute(CREATE_CHANNELS)
        await db_conn.commit()


async def add_user_if_not_exists(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db_conn.commit()


async def set_user_language(user_id: int, lang: str):
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
        await db_conn.commit()


async def get_user_language(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cur = await db_conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def get_all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cur = await db_conn.execute("SELECT user_id FROM users")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def count_users():
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cur = await db_conn.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0]


async def add_channel(chat_id: str, title: str, url: str):
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("INSERT INTO channels (chat_id, title, url) VALUES (?, ?, ?)", (chat_id, title, url))
        await db_conn.commit()


async def remove_channel(channel_db_id: int):
    async with aiosqlite.connect(DB_PATH) as db_conn:
        await db_conn.execute("DELETE FROM channels WHERE id = ?", (channel_db_id,))
        await db_conn.commit()


async def get_channels():
    async with aiosqlite.connect(DB_PATH) as db_conn:
        cur = await db_conn.execute("SELECT id, chat_id, title, url FROM channels")
        return await cur.fetchall()


# ============================================================
# utils/localization.py
# ============================================================
TEXTS = {
    "choose_language": {"uz": "🌐 Tilni tanlang:", "ru": "🌐 Выберите язык:", "en": "🌐 Choose your language:"},
    "language_set": {"uz": "✅ Til o'zbekcha qilib o'rnatildi.", "ru": "✅ Язык установлен: русский.", "en": "✅ Language set to English."},
    "subscribe_required": {"uz": "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling, so'ng «✅ Tekshirish» tugmasini bosing:", "ru": "⚠️ Чтобы пользоваться ботом, подпишитесь на каналы ниже, затем нажмите «✅ Проверить»:", "en": "⚠️ To use the bot, subscribe to the channels below, then press «✅ Check»:"},
    "check_button": {"uz": "✅ Tekshirish", "ru": "✅ Проверить", "en": "✅ Check"},
    "not_subscribed": {"uz": "❌ Siz hali barcha kanallarga a'zo bo'lmadingiz.", "ru": "❌ Вы ещё не подписались на все каналы.", "en": "❌ You haven't subscribed to all channels yet."},
    "main_menu": {"uz": "🏠 Asosiy menyu. Kerakli bo'limni tanlang:", "ru": "🏠 Главное меню. Выберите раздел:", "en": "🏠 Main menu. Choose a section:"},
    "btn_search_song": {"uz": "🎵 Qo'shiq qidirish", "ru": "🎵 Поиск музыки", "en": "🎵 Search Music"},
    "btn_downloader": {"uz": "📥 Instagram / TikTok / YouTube", "ru": "📥 Instagram / TikTok / YouTube", "en": "📥 Instagram / TikTok / YouTube"},
    "btn_round_video": {"uz": "⭕️ Dumaloq video", "ru": "⭕️ Круглое видео", "en": "⭕️ Round video"},
    "btn_language": {"uz": "🌐 Til", "ru": "🌐 Язык", "en": "🌐 Language"},
    "btn_admin": {"uz": "🛠 Admin panel", "ru": "🛠 Админ панель", "en": "🛠 Admin panel"},
    "search_song_prompt": {"uz": "🔎 Qo'shiq nomini yoki ijrochi ismini yozing, yoki video/audio yuboring — men uni topaman.", "ru": "🔎 Введите название песни, имя исполнителя или отправьте видео/аудио — я найду её.", "en": "🔎 Type a song name, artist name, or send a video/audio — I'll find it."},
    "searching": {"uz": "🔎 Qidirilmoqda...", "ru": "🔎 Идёт поиск...", "en": "🔎 Searching..."},
    "nothing_found": {"uz": "😔 Hech narsa topilmadi.", "ru": "😔 Ничего не найдено.", "en": "😔 Nothing found."},
    "recognizing": {"uz": "🎧 Qo'shiq aniqlanmoqda, biroz kuting...", "ru": "🎧 Определяю трек, подождите...", "en": "🎧 Recognizing the track, please wait..."},
    "recognized": {"uz": "🎶 Topildi:", "ru": "🎶 Найдено:", "en": "🎶 Found:"},
    "not_recognized": {"uz": "😔 Qo'shiqni aniqlab bo'lmadi.", "ru": "😔 Не удалось распознать трек.", "en": "😔 Couldn't recognize the track."},
    "downloading": {"uz": "⏳ Yuklanmoqda...", "ru": "⏳ Загрузка...", "en": "⏳ Downloading..."},
    "send_link": {"uz": "🔗 Instagram, TikTok yoki YouTube havolasini yuboring:", "ru": "🔗 Отправьте ссылку на Instagram, TikTok или YouTube:", "en": "🔗 Send an Instagram, TikTok, or YouTube link:"},
    "send_square_video": {"uz": "⭕️ Kvadrat videoni yuboring — men uni dumaloq video qilib beraman.", "ru": "⭕️ Отправьте видео — я превращу его в круглое видеосообщение.", "en": "⭕️ Send a video — I'll turn it into a round video message."},
    "processing_video": {"uz": "⚙️ Video qayta ishlanmoqda...", "ru": "⚙️ Обработка видео...", "en": "⚙️ Processing video..."},
    "song_in_video": {"uz": "🎵 Bu videodagi qo'shiqni yuklab olish", "ru": "🎵 Скачать песню из этого видео", "en": "🎵 Download the song from this video"},
    "next_button": {"uz": "➡️ Keyingisi", "ru": "➡️ Далее", "en": "➡️ Next"},
    "prev_button": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад", "en": "⬅️ Back"},
}


def t(key: str, lang: str) -> str:
    return TEXTS.get(key, {}).get(lang or "uz", key)


# ============================================================
# utils/states.py
# ============================================================
class SearchStates(StatesGroup):
    waiting_query = State()


class DownloaderStates(StatesGroup):
    waiting_link = State()


class RoundVideoStates(StatesGroup):
    waiting_video = State()


class AdminBroadcastStates(StatesGroup):
    waiting_content = State()
    confirming = State()


class AdminChannelStates(StatesGroup):
    waiting_channel = State()


# ============================================================
# Keyboards
# ============================================================
def main_menu_kb(lang: str, user_id: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=t("btn_search_song", lang))],
        [KeyboardButton(text=t("btn_downloader", lang)), KeyboardButton(text=t("btn_round_video", lang))],
        [KeyboardButton(text=t("btn_language", lang))],
    ]
    if user_id in ADMIN_IDS:
        rows.append([KeyboardButton(text=t("btn_admin", lang))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def language_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    b.button(text="🇷🇺 Русский", callback_data="lang_ru")
    b.button(text="🇬🇧 English", callback_data="lang_en")
    return b.adjust(1).as_markup()


def subscribe_kb(channels, lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for _id, chat_id, title, url in channels:
        b.button(text=f"➕ {title or chat_id}", url=url)
    b.button(text=t("check_button", lang), callback_data="check_subscription")
    return b.adjust(1).as_markup()


def songs_page_kb(results, page: int, lang: str, prefix: str = "song") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * SONGS_PER_PAGE
    end = start + SONGS_PER_PAGE
    page_items = results[start:end]
    for idx, _track in enumerate(page_items, start=1):
        b.button(text=str(idx), callback_data=f"{prefix}_pick_{start + idx - 1}")
    b.adjust(5)
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text=t("prev_button", lang), callback_data=f"{prefix}_page_{page - 1}"))
    if end < len(results):
        nav_row.append(InlineKeyboardButton(text=t("next_button", lang), callback_data=f"{prefix}_page_{page + 1}"))
    if nav_row:
        b.row(*nav_row)
    return b.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📢 Reklama yuborish", callback_data="admin_broadcast")
    b.button(text="📋 Kanallar ro'yxati", callback_data="admin_channels_list")
    b.button(text="➕ Kanal qo'shish", callback_data="admin_channel_add")
    b.button(text="📊 Statistika", callback_data="admin_stats")
    return b.adjust(1).as_markup()


def channels_manage_kb(channels) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for ch_id, chat_id, title, url in channels:
        b.button(text=f"❌ {title or chat_id}", callback_data=f"admin_channel_del_{ch_id}")
    return b.adjust(1).as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborish", callback_data="broadcast_confirm")
    b.button(text="❌ Bekor qilish", callback_data="broadcast_cancel")
    return b.adjust(2).as_markup()


# ============================================================
# Services (Biznes Logika)
# ============================================================
os.makedirs(TEMP_DIR, exist_ok=True)


def search_tracks(query: str, limit: int = 50):
    url = "https://itunes.apple.com/search"
    params = {"term": query, "media": "music", "entity": "song", "limit": limit}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    results = []
    for item in resp.json().get("results", []):
        results.append({
            "title": item.get("trackName"),
            "artist": item.get("artistName"),
            "preview_url": item.get("previewUrl"),
        })
    return results


async def recognize_from_file(file_path: str):
    try:
        shazam_wav = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}_shazam.wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", file_path,
            "-ss", "0", "-t", "4",
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            shazam_wav
        ], check=True, capture_output=True)

        if not os.path.exists(shazam_wav):
            return None

        with open(shazam_wav, "rb") as f:
            raw_bytes = f.read()

        if os.path.exists(shazam_wav):
            os.remove(shazam_wav)

        url = "https://amp.shazam.com/discovery/v5/en-US/UZ/iphone/-/tag/sample"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
            "Content-Type": "application/octet-stream"
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(url, headers=headers, data=raw_bytes, timeout=15))

        if response.status_code == 200:
            data = response.json()
            if "track" in data:
                return {"title": data["track"].get("title"), "artist": data["track"].get("subtitle")}
        return None
    except Exception as e:
        logging.error(f"Shazam xatoligi: {e}")
        return None


def download_track_audio(title: str, artist: str) -> str:
    query = f"ytsearch1:{artist} {title} audio"
    out_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([query])
    return out_path.replace("%(ext)s", "mp3")


def download_media(url: str) -> str:
    out_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {"format": "bestvideo+bestaudio/best", "outtmpl": out_path, "quiet": True, "merge_output_format": "mp4", "noplaylist": True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    if not os.path.exists(filename):
        filename = os.path.splitext(filename)[0] + ".mp4"
    return filename


def extract_audio(video_path: str) -> str:
    audio_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.wav")
    subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-ar", "44100", "-ac", "2", audio_path], check=True, capture_output=True)
    return audio_path


def to_round_video(input_path: str) -> str:
    out_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}_round.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "crop='min(in_w,in_h)':'min(in_w,in_h)',scale=640:640",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", "-t", "60", out_path
    ], check=True, capture_output=True)
    return out_path


# ============================================================
# Handlers (Asosiy muloqot va qidiruv tizimi)
# ============================================================
start_router = Router()


async def is_subscribed(bot, user_id: int) -> bool:
    channels = await get_channels()
    if not channels:
        return True
    for _id, chat_id, _title, _url in channels:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True


async def show_subscribe_prompt(message_or_cb, lang: str):
    channels = await get_channels()
    if hasattr(message_or_cb, "message"):
        await message_or_cb.message.answer(t("subscribe_required", lang), reply_markup=subscribe_kb(channels, lang))
    else:
        await message_or_cb.answer(t("subscribe_required", lang), reply_markup=subscribe_kb(channels, lang))


@start_router.message(CommandStart())
async def cmd_start(message: Message):
    await add_user_if_not_exists(message.from_user.id)
    lang = await get_user_language(message.from_user.id)
    if not lang:
        await message.answer(t("choose_language", "uz"), reply_markup=language_kb())
        return
    if not await is_subscribed(message.bot, message.from_user.id):
        await show_subscribe_prompt(message, lang)
        return
    await message.answer(t("main_menu", lang), reply_markup=main_menu_kb(lang, message.from_user.id))


@start_router.callback_query(F.data.startswith("lang_"))
async def set_language(call: CallbackQuery):
    lang = call.data.split("_")[1]
    await set_user_language(call.from_user.id, lang)
    await call.message.delete()
    if not await is_subscribed(call.bot, call.from_user.id):
        await show_subscribe_prompt(call, lang)
        return
    await call.message.answer(t("main_menu", lang), reply_markup=main_menu_kb(lang, call.from_user.id))


@start_router.callback_query(F.data == "check_subscription")
async def check_subscription(call: CallbackQuery):
    lang = await get_user_language(call.from_user.id) or "uz"
    if await is_subscribed(call.bot, call.from_user.id):
        await call.message.delete()
        await call.message.answer(t("main_menu", lang), reply_markup=main_menu_kb(lang, call.from_user.id))
    else:
        await call.answer(t("not_subscribed", lang), show_alert=True)


@start_router.message(F.text.in_({"🌐 Til", "🌐 Язык", "🌐 Language"}))
async def change_language(message: Message):
    await message.answer(t("choose_language", "uz"), reply_markup=language_kb())


# --- Qidiruv qismi ---
music_search_router = Router()


@music_search_router.message(F.text.in_({"🎵 Qo'shiq qidirish", "🎵 Поиск музыки", "🎵 Search Music"}))
async def start_search(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(t("search_song_prompt", lang))
    await state.set_state(SearchStates.waiting_query)


async def send_results_page(message: Message, results, page: int, lang: str):
    if not results:
        await message.answer(t("nothing_found", lang))
        return
    start = page * 10
    page_items = results[start:start + 10]
    lines = [f"{i + 1}. {tr['title']} — {tr['artist']}" for i, tr in enumerate(page_items)]
    await message.answer("\n".join(lines), reply_markup=songs_page_kb(results, page, lang))


@music_search_router.message(SearchStates.waiting_query, F.text)
async def handle_text_query(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(t("searching", lang))
    results = search_tracks(message.text)
    await state.update_data(results=results)
    await send_results_page(message, results, 0, lang)


@music_search_router.message(SearchStates.waiting_query, F.voice | F.audio)
async def handle_voice_query(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(t("recognizing", lang))
    file = message.voice or message.audio
    tg_file = await message.bot.get_file(file.file_id)
    local_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.ogg")
    await message.bot.download_file(tg_file.file_path, local_path)
    track = await recognize_from_file(local_path)
    if os.path.exists(local_path):
        os.remove(local_path)
    if not track:
        await message.answer(t("not_recognized", lang))
        return
    results = search_tracks(f"{track['artist']} {track['title']}")
    await state.update_data(results=results)
    await message.answer(f"{t('recognized', lang)} {track['title']} — {track['artist']}")
    await send_results_page(message, results, 0, lang)


@music_search_router.message(SearchStates.waiting_query, F.video | F.video_note)
async def handle_video_query(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(t("recognizing", lang))
    file = message.video or message.video_note
    tg_file = await message.bot.get_file(file.file_id)
    local_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.mp4")
    await message.bot.download_file(tg_file.file_path, local_path)
    audio_path = extract_audio(local_path)
    track = await recognize_from_file(audio_path)
    if os.path.exists(local_path):
        os.remove(local_path)
    if os.path.exists(audio_path):
        os.remove(audio_path)
    if not track:
        await message.answer(t("not_recognized", lang))
        return
    results = search_tracks(f"{track['artist']} {track['title']}")
    await state.update_data(results=results)
    await message.answer(f"{t('recognized', lang)} {track['title']} — {track['artist']}")
    await send_results_page(message, results, 0, lang)


@music_search_router.callback_query(F.data.startswith("song_page_"))
async def paginate_songs(call: CallbackQuery, state: FSMContext):
    lang = await get_user_language(call.from_user.id) or "uz"
    page = int(call.data.split("_")[-1])
    data = await state.get_data()
    results = data.get("results", [])
    start = page * 10
    page_items = results[start:start + 10]
    lines = [f"{i + 1}. {tr['title']} — {tr['artist']}" for i, tr in enumerate(page_items)]
    await call.message.edit_text("\n".join(lines), reply_markup=songs_page_kb(results, page, lang))


@music_search_router.callback_query(F.data.startswith("song_pick_"))
async def pick_song(call: CallbackQuery, state: FSMContext):
    lang = await get_user_language(call.from_user.id) or "uz"
    index = int(call.data.split("_")[-1])
    data = await state.get_data()
    results = data.get("results", [])
    if index >= len(results):
        return
    track = results[index]
    status_msg = await call.message.answer(t("downloading", lang))
    try:
        path = download_track_audio(track["title"], track["artist"])
        await call.message.answer_audio(
            FSInputFile(path, filename=f"{track['artist']} - {track['title']}.mp3"),
            title=track["title"], performer=track["artist"]
        )
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        await call.message.answer(f"⚠️ Xatolik: {e}")
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass


# --- Downloader va Round Video ---
downloader_router = Router()


@downloader_router.message(F.text.in_({"📥 Instagram / TikTok / YouTube"}))
async def start_downloader(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(t("send_link", lang))
    await state.set_state(DownloaderStates.waiting_link)


@downloader_router.message(DownloaderStates.waiting_link, F.text)
async def handle_link(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    status_msg = await message.answer(t("downloading", lang))
    try:
        video_path = download_media(message.text.strip())
        await message.answer_video(FSInputFile(video_path))
        await state.update_data(last_video_path=video_path)
        b = InlineKeyboardBuilder().button(text=t("song_in_video", lang), callback_data="identify_video_song")
        await message.answer(t("song_in_video", lang), reply_markup=b.as_markup())
    except Exception as e:
        await message.answer(f"⚠️ Xatolik: {e}")
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass


@downloader_router.callback_query(F.data == "identify_video_song")
async def identify_song_in_video(call: CallbackQuery, state: FSMContext):
    lang = await get_user_language(call.from_user.id) or "uz"
    data = await state.get_data()
    video_path = data.get("last_video_path")
    if not video_path or not os.path.exists(video_path):
        return
    await call.message.answer(t("recognizing", lang))
    audio_path = extract_audio(video_path)
    track = await recognize_from_file(audio_path)
    if os.path.exists(audio_path):
        os.remove(audio_path)
    if not track:
        await call.message.answer(t("not_recognized", lang))
        return
    await call.message.answer(f"{t('recognized', lang)} {track['title']} — {track['artist']}")
    try:
        mp3_path = download_track_audio(track["title"], track["artist"])
        await call.message.answer_audio(
            FSInputFile(mp3_path, filename=f"{track['artist']} - {track['title']}.mp3"),
            title=track["title"], performer=track["artist"]
        )
        if os.path.exists(mp3_path):
            os.remove(mp3_path)
    except Exception as e:
        await call.message.answer(f"⚠️ Xatolik: {e}")


round_video_router = Router()


@round_video_router.message(F.text.in_({"⭕️ Dumaloq video", "⭕️ Круглое видео"}))
async def start_round_video(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    await message.answer(t("send_square_video", lang))
    await state.set_state(RoundVideoStates.waiting_video)


@round_video_router.message(RoundVideoStates.waiting_video, F.video)
async def handle_round_video(message: Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id) or "uz"
    status_msg = await message.answer(t("processing_video", lang))
    tg_file = await message.bot.get_file(message.video.file_id)
    local_path = os.path.join(TEMP_DIR, f"{uuid.uuid4().hex}.mp4")
    await message.bot.download_file(tg_file.file_path, local_path)
    try:
        round_path = to_round_video(local_path)
        await message.answer_video_note(FSInputFile(round_path))
        if os.path.exists(round_path):
            os.remove(round_path)
    except Exception as e:
        await message.answer(f"⚠️ Xatolik: {e}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
        try:
            await status_msg.delete()
        except Exception:
            pass
    await state.clear()


# --- Admin Panel ---
admin_router = Router()


@admin_router.message(F.text.in_({"🛠 Admin panel", "🛠 Админ панель"}))
async def open_admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("🛠 Admin panel:", reply_markup=admin_panel_kb())


@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    count = await count_users()
    await call.message.answer(f"📊 Jami foydalanuvchilar: {count}")
    await call.answer()


@admin_router.callback_query(F.data == "admin_channels_list")
async def admin_channels_list(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    channels = await get_channels()
    if not channels:
        await call.message.answer("📋 Majburiy kanal yo'q.")
    else:
        await call.message.answer("📋 Kanalni o'chirish uchun bosing:", reply_markup=channels_manage_kb(channels))
    await call.answer()


@admin_router.callback_query(F.data == "admin_channel_add")
async def admin_channel_add_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.message.answer("➕ Format: `@username | https://t.me/url | Nomi`")
    await state.set_state(AdminChannelStates.waiting_channel)


@admin_router.message(AdminChannelStates.waiting_channel, F.text)
async def admin_channel_add_finish(message: Message, state: FSMContext):
    parts = [p.strip() for p in message.text.split("|")]
    if len(parts) < 2:
        return
    await add_channel(parts[0], parts[2] if len(parts) > 2 else parts[0], parts[1])
    await message.answer("✅ Kanal qo'shildi.")
    await state.clear()


@admin_router.callback_query(F.data.startswith("admin_channel_del_"))
async def admin_channel_delete(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await remove_channel(int(call.data.split("_")[-1]))
    await call.answer("✅ O'chirildi")


@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.message.answer("📢 Reklama xabarini yuboring.")
    await state.set_state(AdminBroadcastStates.waiting_content)


@admin_router.message(AdminBroadcastStates.waiting_content)
async def admin_broadcast_preview(message: Message, state: FSMContext):
    await state.update_data(broadcast_chat_id=message.chat.id, broadcast_msg_id=message.message_id)
    await message.answer("Tasdiqlaysizmi?", reply_markup=broadcast_confirm_kb())
    await state.set_state(AdminBroadcastStates.confirming)


@admin_router.callback_query(AdminBroadcastStates.confirming, F.data == "broadcast_confirm")
async def admin_broadcast_send(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_ids = await get_all_user_ids()
    sent = 0
    for uid in user_ids:
        try:
            await call.bot.copy_message(chat_id=uid, from_chat_id=data["broadcast_chat_id"], message_id=data["broadcast_msg_id"])
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await call.message.answer(f"✅ {sent} ta foydalanuvchiga yuborildi.")
    await state.clear()


# ============================================================
# Asosiy main() funksiyasi
# ============================================================
async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_routers(admin_router, start_router, music_search_router, downloader_router, round_video_router)
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot Python 3.13 rejimida muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())