import os, requests
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

def send(m):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": m})

try:
    r = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}", timeout=15).json()
    tickers = r.get('tickers', [])[:10]
    msg = f"🔍 اختبار: لقيت {len(tickers)} سهم\n\n"
    for t in tickers[:5]:
        msg += f"{t.get('ticker')} ${t.get('day',{}).get('c',0)} +{t.get('todaysChangePerc',0):.1f}%\n"
    send(msg)
except Exception as e:
    send(f"❌ خطأ: {e}")
