import os
import requests
import yt_dlp
import logging
import time
import json
from urllib.parse import urlparse
from flask import Flask
from threading import Thread

# ---- إعدادات البوت ----
TOKEN = "7602453003:AAGBMn4AvgsWmShuIujlYKcWBxdjpMdKAyw"  # ضع التوكن هنا
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

# إعدادات التسجيل
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ملف لتخزين المشتركين
USERS_FILE = 'subscribers.json'

# تحميل المشتركين من الملف (إن وجد)
def load_subscribers():
    if os.path.isfile(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

# حفظ المشتركين في الملف
def save_subscribers(subscribers):
    with open(USERS_FILE, 'w') as f:
        json.dump(subscribers, f)

# ---- خادم ويب لإبقاء البوت نشطًا ----
@app.route("/")
def home():
    return "Bot is Running!"

# ---- وظائف البوت ----
def download_media(url, user_id):
    try:
        ydl_opts = {
            "format": "best[ext=mp4]/bestaudio[ext=m4a]",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "ignoreerrors": True,
            "no_check_certificate": True,
            "retries": 5,
            "http_headers": {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.google.com/",
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("❌ فشل استخراج المعلومات")

        # البحث عن اسم الملف المحمل
        filename = None
        if "requested_downloads" in info:
            for file_info in info["requested_downloads"]:
                if file_info.get("ext") == "mp4":
                    filename = file_info["filepath"]
                    break

        if not filename or not os.path.isfile(filename):
            raise Exception("⚠️ تعذر تحديد اسم الملف المحمل.")

        logger.info(f"✅ تم تحميل الملف: {filename}")
        send_file(user_id, filename)

    except Exception as e:
        logger.error(f"❌ خطأ في التحميل: {str(e)}")
        send_message(user_id, f"❌ فشل التحميل: {str(e)}")

def process_updates(offset):
    try:
        response = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 30})
        updates = response.json()
        if not updates.get("ok", False):
            logger.error(f"❌ فشل جلب التحديثات: {updates}")
            return offset

        for update in updates.get("result", []):
            update_id = update["update_id"]
            message = update.get("message", {})
            text = message.get("text", "").strip()
            user_id = message.get("from", {}).get("id")
            if not user_id or not text:
                continue

            # إضافة المستخدم عند أول استخدام
            subscribers = load_subscribers()
            if user_id not in subscribers:
                subscribers[user_id] = {"username": message.get("from", {}).get("username", "غير معروف")}
                save_subscribers(subscribers)

            if text == "/start":
                send_welcome(user_id)
            elif text == "/help":
                send_help(user_id)
            elif text.startswith(("/admin", "/stats", "/subscribers")):
                if user_id == 7110791257:  # معرفك كأدمن هنا
                    handle_admin_commands(text, user_id)
            elif text.startswith(("http://", "https://")):
                handle_url(text, user_id)

            offset = update_id + 1

        return offset
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة التحديثات: {str(e)}")
        return offset

def handle_admin_commands(command, user_id):
    subscribers = load_subscribers()

    if command.startswith("/stats"):
        total_users = len(subscribers)
        send_message(user_id, f"عدد المشتركين في البوت: {total_users}")
    elif command.startswith("/subscribers"):
        subscriber_list = "\n".join([f"ID: {user_id}, Username: {info['username']}" for user_id, info in subscribers.items()])
        send_message(user_id, f"قائمة المشتركين:\n{subscriber_list}")
    elif command.startswith("/remove"):
        user_to_remove = int(command.split()[1])
        if user_to_remove in subscribers:
            del subscribers[user_to_remove]
            save_subscribers(subscribers)
            send_message(user_id, f"تم حذف المستخدم {user_to_remove} بنجاح.")
        else:
            send_message(user_id, "المستخدم غير موجود.")
    else:
        send_message(user_id, "أمر غير معروف.")

def send_welcome(user_id):
    message = """🌟 *مرحبًا بك في بوت التحميل الذكي!*
    أرسل رابط فيديو من:
    - YouTube - TikTok - Instagram - Facebook - Twitter X
    """
    send_message(user_id, message)

def send_help(user_id):
    message = """🛠 *الأوامر المتاحة:*
    /start - بدء استخدام البوت
    /help - عرض المساعدة
    /stats - عرض إحصائيات البوت
    /subscribers - عرض قائمة المشتركين
    /remove <user_id> - حذف مستخدم من قائمة المشتركين
    """
    send_message(user_id, message)

def handle_url(url, user_id):
    domain = urlparse(url).netloc.lower()
    supported_platforms = [
        "youtube.com", "youtu.be",
        "tiktok.com", "instagram.com",
        "facebook.com", "fb.watch",
        "twitter.com", "x.com"  # إضافة X (تويتر سابقًا)
    ]

    if any(platform in domain for platform in supported_platforms):
        send_message(user_id, "⏳ جاري التحميل...")
        download_media(url, user_id)
    else:
        send_message(user_id, "⚠️ المنصة غير مدعومة!")

def send_message(user_id, text):
    try:
        response = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": user_id, "text": text, "parse_mode": "Markdown"},
        )
        if response.status_code != 200:
            logger.error(f"❌ فشل إرسال الرسالة: {response.text}")
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الرسالة: {str(e)}")

def send_file(user_id, file_path):
    try:
        if not os.path.isfile(file_path):
            logger.error(f"❌ الملف غير موجود: {file_path}")
            send_message(user_id, "❌ فشل تحميل الفيديو. الرجاء المحاولة لاحقًا.")
            return
        with open(file_path, "rb") as f:
            files = {"video": f}
            response = requests.post(
                f"{BASE_URL}/sendVideo",
                data={"chat_id": user_id},
                files=files,
                timeout=30,
            )
            if response.status_code != 200:
                logger.error(f"❌ فشل إرسال الملف: {response.text}")
                send_message(user_id, "❌ فشل إرسال الملف. الرجاء المحاولة لاحقًا.")
            else:
                os.remove(file_path)
    except Exception as e:
        logger.error(f"❌ خطأ في الإرسال: {str(e)}")
        send_message(user_id, "❌ حدث خطأ غير متوقع أثناء الإرسال.")

# ---- التشغيل الرئيسي ----
if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    logger.info("🚀 تم بدء البوت...")
    offset = 0
    while True:
        try:
            offset = process_updates(offset)
            time.sleep(2)
        except Exception as e:
            logger.error(f"❌ خطأ في الحلقة الرئيسية: {str(e)}")
            time.sleep(10)
