import requests, time, schedule, os
from datetime import datetime, timedelta

POLYGON_KEY = os.getenv("POLYGON_KEY", "ضع_مفتاحك_هنا")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ضع_التوكن_هنا")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT", "ضع_الايدي_هنا")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def job():
    try:
        now = datetime.now()
        hour = now.hour
        if 3 <= hour < 11:
            print(f"{now.strftime('%H:%M')} - نايم")
            return
        print(f"{now.strftime('%H:%M')} - يفحص...")
        # هنا تحطين دالة scan حقتك
        # مؤقتا نرسل رسالة تجربة
        # send_telegram(f"فحص {now.strftime('%H:%M')} KSA")
    except Exception as e:
        print(f"Error in job: {e}")
        time.sleep(5) # لا يكرش

# تشغيل
print("Bot started!")
send_telegram("✅ V11 اشتغل - من 11 الصبح الى 3 الفجر KSA")

schedule.every(5).minutes.do(job)
job()

while True:
    try:
        schedule.run_pending()
        time.sleep(30)
    except Exception as e:
        print(f"Loop error: {e}")
        time.sleep(30)
