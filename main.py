import os, time
print("Starting bot... checking libs")

# يجرب يستورد، لو فشل يثبت
try:
    import requests, schedule
except:
    print("Installing libs...")
    os.system("pip install requests schedule")
    import requests, schedule

from datetime import datetime

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT = os.getenv("TELEGRAM_CHAT", "")
POLY = os.getenv("POLYGON_KEY", "")

print(f"TOKEN exists: {bool(TOKEN)}")
print(f"CHAT exists: {bool(CHAT)}")

def send(msg):
    if not TOKEN or not CHAT:
        print(f"Would send: {msg}")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT, "text": msg}, timeout=10)
        print("Sent to Telegram")
    except Exception as e:
        print(f"Send failed: {e}")

send("✅ البوت اشتغل على Koyeb - من 11 الصبح الى 3 الفجر")

# حلقة ما تكرش
while True:
    try:
        now = datetime.now()
        hour = now.hour
        if 3 <= hour < 11:
            print(f"{now.strftime('%H:%M')} sleeping")
        else:
            print(f"{now.strftime('%H:%M')} awake - would scan here")
        time.sleep(60)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)
