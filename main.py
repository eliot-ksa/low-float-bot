import os, time, requests, pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

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
    if 3 <= h < 11:
        return False
    return True

def scan_polygon():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=15).json()
        tickers = r.get('tickers', [])[:15]
        found = []
        for t in tickers:
            sym = t.get('ticker')
            price = t.get('day', {}).get('c', 0)
            vol = t.get('day', {}).get('v', 0)
            # فلتر low float بسيط + فوليوم عالي
            if vol > 500000 and 1 < price < 20:
                found.append(f"{sym} - ${price} Vol:{vol}")
        return found
    except Exception as e:
        print(f"Polygon Error: {e}")
        return []

send("🚀 البوت اشتغل بنجاح على Railway\nالفحص الديناميكي من 11ص لـ 3ص بتوقيت الرياض ✅")
print("Bot Started...")

while True:
    try:
        if not is_allowed():
            print(f"⏸️ نايم - خارج وقت 11ص-3ص")
            time.sleep(60)
            continue

        now = datetime.now().strftime('%H:%M:%S')
        print(f"🔍 [{now}] جاري فحص السوق...")

        stocks = scan_polygon()
        for s in stocks:
            send(f"🎯 فرصة Low Float:\n{s}")

        time.sleep(60)
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(10)
