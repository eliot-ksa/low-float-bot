import os, time, requests, pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        print(f"Sent: {msg[:80]}")
    except Exception as e:
        print(f"Send Error: {e}")

def is_allowed():
    tz = pytz.timezone('Asia/Riyadh')
    h = datetime.now(tz).hour
    # يوقف فقط من 3 الفجر الى 11 الصباح
    if 3 <= h < 11:
        return False
    return True

send("🚀 البوت اشتغل بنجاح على Railway\nالفحص الديناميكي من 11ص لـ 3ص بتوقيت الرياض ✅")
print("Bot Started...")

while True:
    try:
        if not is_allowed():
            print("⏸️ نايم - خارج وقت العمل 11ص-3ص")
            time.sleep(60)
            continue

        now_str = datetime.now().strftime('%H:%M:%S')
        print(f"🔍 [{now_str}] جاري فحص الاسهم Low Float...")

        # --- هنا كود Polygon الاصلي حقك ---
        # اذا كان عندك كود قديم للفحص حطه هنا
        # مثال:
        # tickers = get_low_float_tickers()
        # for t in tickers:
        #     if check_volume(t):
        #         send(f"🎯 {t} ...")

        # رسالة heartbeat كل 15 دقيقة عشان تتأكد انه شغال (تقدر تحذفها بعدين)
        if datetime.now().minute % 15 == 0:
            print("✅ Bot is alive and scanning...")

        time.sleep(60)
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(10)
