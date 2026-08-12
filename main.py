import os, time, requests
from datetime import datetime
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        print(f"Sent: {msg[:100]}")
    except Exception as e:
        print(f"Send Error: {e}")

def is_allowed():
    tz = pytz.timezone('Asia/Riyadh')
    now = datetime.now(tz)
    h = now.hour
    # يوقف من 3 الفجر لـ 11 الصباح فقط
    if 3 <= h < 11:
        return False
    return True

# رسالة بداية
send("🚀 البوت اشتغل بنجاح على Railway\nالفحص الديناميكي من 11ص لـ 3ص بتوقيت الرياض ✅")
print("Bot Started...")

while True:
    try:
        if not is_allowed():
            tz = pytz.timezone('Asia/Riyadh')
            now = datetime.now(tz)
            print(f"⏸️ خارج الوقت {now.strftime('%I:%M %p')} نايم (3ص-11ص)")
            time.sleep(60)
            continue

        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] جاري فحص الاسهم Low Float...")
        
        # هنا كود فحص Polygon حقك القديم - حطه هنا
        # مثال مؤقت عشان تتأكد انه شغال:
        # لو تبي اختبار، فك التعليق عن السطر الجاي:
        # send("✅ فحص حي - البوت شغال الان")
        
        time.sleep(60)  # يفحص كل دقيقة

    except Exception as e:
        print(f"❌ Error in loop: {e}")
        time.sleep(10)
