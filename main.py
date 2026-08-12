import os, time, requests, pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg}, timeout=15)
        print(f"Sent: {msg[:80]}")
    except Exception as e:
        print(f"Send Error: {e}")

def is_allowed():
    tz = pytz.timezone('Asia/Riyadh')
    h = datetime.now(tz).hour
    if 3 <= h < 11:  # ينام من 3 الفجر لـ 11 الصباح
        return False
    return True

send("🚀 البوت اشتغل بنجاح على Railway\nالفحص الديناميكي من 11ص لـ 3ص بتوقيت الرياض ✅")
print("Bot Started...")

# عشان ما يعلق
while True:
    try:
        if not is_allowed():
            print(f"⏸️ نايم - الساعة {datetime.now().strftime('%H:%M')} خارج وقت 11ص-3ص")
            time.sleep(60)
            continue

        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] جاري فحص السوق...")

        # --- هنا تقدر تضيف كود Polygon حقك لاحقاً ---
        # حالياً هذا يثبت ان البوت حي وما يطفي
        
        time.sleep(60)

    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(10)
