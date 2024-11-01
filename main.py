import os
import json
import redis
import yt_dlp
import asyncio
from concurrent.futures import ThreadPoolExecutor
from hydrogram import Client, filters
from hydrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from dotenv import load_dotenv


URL_PATTERN = r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$"

def get_env(key):
    value = os.environ.get(key)
    if value is None or value.strip() == "":
        print(f"{key} can't be empty")
        os._exit(1)
    return value

def load_config():
    return {
        "REDIS_HOST": get_env("REDIS_HOST"),
        "REDIS_PORT": get_env("REDIS_PORT"),
        "API_ID": get_env("API_ID"),
        "API_HASH": get_env("API_HASH"),
        "BOT_TOKEN": get_env("BOT_TOKEN"),
    }

load_dotenv()
config = load_config()

r = redis.Redis(
    host=config["REDIS_HOST"], 
    port=config["REDIS_PORT"], 
    db=0, 
    decode_responses=True
)

try:
    r.ping()
    print("[+] Connected to redis...")
except redis.ConnectionError as e:
    print(f"[-] Failed to connect redis: {e}")
    os._exit(1)

app = Client(
    "pixel",
    api_id=config["API_ID"],
    api_hash=config["API_HASH"],
    bot_token=config["BOT_TOKEN"],
)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(c: Client, m: Message):
    text = """
Just send Youtube video URL.
"""
    await m.reply_text(text)


@app.on_message(filters.regex(URL_PATTERN) & filters.private)
async def download_handler(c: Client, m: Message):
    key = f"user:{m.chat.id}"
    r.setex(key, 300, json.dumps({"url": m.text, "format": None}))

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Audio", callback_data="format_audio"),
                InlineKeyboardButton("Video", callback_data="format_video"),
            ],
        ],
    )

    await m.reply_text("Select format:", reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"^format_"))
async def format_selection(c: Client, cb: CallbackQuery):
    key = f"user:{cb.message.chat.id}"
    user_data = json.loads(r.get(key) or "{}")

    if not user_data.get("url"):
        await cb.answer("Link expired. Please send the link again.")
        return

    if cb.data == "format_audio":
        user_data["format"] = "audio"

        r.setex(key, 300, json.dumps(user_data))

        await cb.message.edit_reply_markup(None)
        await cb.message.edit_text("Downloading started...")

        file_path, thumbnail_path, title = await download_audio(user_data["url"])

        if os.path.exists(file_path):
            try:
                await cb.message.edit_text("Uploading to telegram...")
                await app.send_audio(
                    cb.message.chat.id, file_path, thumb=thumbnail_path, title=title
                )
            except:
                await cb.message.edit_text("Uploading failed!")
            finally:
                os.remove(file_path)
                os.remove(thumbnail_path)
        else:
            await cb.message.edit_text("Downloading failed!")

        await cb.message.delete(revoke=True)

    elif cb.data == "format_video":
        user_data["format"] = "video"

        r.setex(key, 300, json.dumps(user_data))

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("480p", callback_data="quality_480p"),
                    InlineKeyboardButton("720p", callback_data="quality_720p"),
                    InlineKeyboardButton("1080p", callback_data="quality_1080p"),
                ]
            ]
        )

        await cb.message.edit_text("Select quality:")
        await cb.message.edit_reply_markup(reply_markup=keyboard)
    else:
        await cb.answer("Invalid format selection.")


@app.on_callback_query(filters.regex(r"^quality_"))
async def quality_selection(c: Client, cb: CallbackQuery):
    key = f"user:{cb.message.chat.id}"
    user_data = json.loads(r.get(key) or "{}")

    if not user_data.get("url") or user_data.get("format") != "video":
        await cb.answer("Selection expired. Please send the link again.")
        return

    quality_map = {
        "quality_480p": "bestvideo[height<=480][width<=854]+bestaudio/best",  # 480p
        "quality_720p": "bestvideo[height<=720][width<=1280]+bestaudio/best",  # 720p
        "quality_1080p": "bestvideo[height<=1080][width<=1920]+bestaudio/best",  # 1080p
    }

    quality = quality_map.get(cb.data)
    if not quality:
        await cb.answer("Invalid quality selection.")
        return

    await cb.message.edit_reply_markup(None)
    await cb.message.edit_text("Downloading started...")

    file_path, thumbnail_path, duration, width, height = await download_video(user_data["url"], quality)

    if os.path.exists(file_path):
        try:
            await cb.message.edit_text("Uploading to telegram...")
            await app.send_video(cb.message.chat.id, file_path, thumb=thumbnail_path, supports_streaming=True, width=width, height=height, duration=duration)
        except:
            await cb.message.edit_text("Uploading failed!")
        finally:
            os.remove(file_path)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
    else:
        await cb.message.edit_text("Downloading failed!")

    await cb.message.delete(revoke=True)


async def download_audio(url):
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "256",
            },
            {
            "key": "FFmpegThumbnailsConvertor",
            "format": "jpg",
            },
        ],
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "writethumbnail": True,
        "quiet": True,
    }

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            new_path = file_path.rsplit(".", 1)[0] + ".mp3"
            title = info_dict.get("title", "Unknown")
            thumbnail_path = file_path.rsplit(".", 1)[0] + ".jpg"

            return new_path, thumbnail_path, title

    loop = asyncio.get_running_loop()
    try:
        with ThreadPoolExecutor() as pool:
            file_path, thumbnail_path, title = await loop.run_in_executor(
                pool, _download
            )

        return file_path, thumbnail_path, title
    except Exception as e:
        print(f"Error: {e}")
        return None, None, None


async def download_video(url, quality):
    os.makedirs('downloads', exist_ok=True)

    ydl_opts = {
        "format": quality,
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            },
            {
            "key": "FFmpegThumbnailsConvertor",
            "format": "jpg",
            },
        ],
        "writethumbnail": True,
        "quiet": True,
    }

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info_dict)
            new_path = file_path.rsplit(".", 1)[0] + ".mp4"
            width = info_dict.get("width", 0)
            height = info_dict.get('height', 0)
            duration = int(info_dict.get("duration", 0))
            thumbnail_path = file_path.rsplit(".", 1)[0] + ".jpg"

            return new_path, thumbnail_path, duration, width, height

    loop = asyncio.get_running_loop()
    try:
        with ThreadPoolExecutor() as pool:
            new_path, thumbnail_path, duration, width, height = await loop.run_in_executor(pool, _download)
        
        return new_path, thumbnail_path, duration, width, height
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == "__main__":
    print("[+] Bot is up and running...")
    app.run()
