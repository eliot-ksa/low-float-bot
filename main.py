import os, time, requests, pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, json=data, timeout=15)
        print(f"Sent: {msg[:80]}")
    except Exception as e:
        print(f"Send Error: {e}")

def is_allowed():
    tz = pytz.timezone('Asia/Riyadh')
    h = datetime.now(tz).hour
    # ينام فقط من 3 الفجر الى 11 الصباح
    if 3 <= h < 11:
        return False
    return True

def scan_polygon():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=20).json()
        tickers = r.get('tickers', [])[:20]
        found = []
        for t in tickers:
            sym = t.get('ticker','')
            day = t.get('day',{})
            price = day.get('c',0)
            vol = day.get('v',0)
            if vol > 800000 and 1 < price < 20:
                change = t.get('todaysChangePerc',0)
                found.append(f"*{sym}* - ${price:.2f} ({change:.1f}%) Vol:{vol/1000000:.1f}M")
        return found
    except Exception as e:
        print(f"Polygon Error: {e}")
        return []

send("🚀 البوت اشتغل بنجاح على Railway\nالفحص من 11ص لـ 3ص بتوقيت الرياض ✅")
print("Bot Started...")

while True:
    try:
        if not is_allowed():
            print("⏸️ نايم - خارج وقت 11ص-3ص")
            time.sleep(60)
            continue

        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] جاري فحص السوق...")

        stocks = scan_polygon()
        if stocks:
            msg = "🎯 *فرص Low Float:*\n\n" + "\n".join(stocks)
            send(msg)
        else:
            print("No candidates")

        time.sleep(60)

    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(10)
