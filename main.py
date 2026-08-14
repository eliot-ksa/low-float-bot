import os, requests
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(e)

def get_float(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json()
        return r.get('results', {}).get('share_class_shares_outstanding', 0)
    except: return 0

def has_news(sym):
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={sym}&limit=2&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10).json()
        return len(r.get('results', [])) > 0
    except: return True

send("🧪 *تست حقيقي - افحص السوق الحين...*")

try:
    url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
    tickers = requests.get(url, timeout=15).json().get('tickers', [])
    send(f"📊 Polygon رجع {len(tickers)} سهم طاير اليوم")

    candidates = []
    for t in tickers[:50]:
        sym = t.get('ticker','')
        price = t.get('day',{}).get('c',0)
        change = t.get('todaysChangePerc',0)
        vol = t.get('day',{}).get('v',0)

        if not sym or len(sym)>5: continue
        
        # فلتر PlayBookTrades
        if not (1.5 <= price <= 10 and change >= 8):
            continue

        f = get_float(sym)
        if f != 0 and f > 10000000: continue

        if not has_news(sym): continue

        candidates.append({'sym': sym, 'price': price, 'change': change, 'float': f})
        send(f"🔍 لقينا: *{sym}* ${price:.2f} +{change:.1f}% Float {f/1000000:.1f}M" if f else f"🔍 لقينا: *{sym}* ${price:.2f} +{change:.1f}%")

    if not candidates:
        send("📭 *التست: ما فيه اسهم تنطبق عليها مواصفات PlayBookTrades الحين*\nالسبب: السوق مقفل او ما فيه Float<10M + خبر\nجرب 4:30م وقت الافتتاح")
    else:
        top = sorted(candidates, key=lambda x: x['change'], reverse=True)[:3]
        msg = f"📘 *PlayBook تست حقيقي {datetime.now().strftime('%H:%M')}*\n\n"
        for i,c in enumerate(top,1):
            msg+=f"{i}. *{c['sym']}* ${c['price']:.2f} +{c['change']:.1f}%\n"
        msg+="\n✅ البوت شغال ويقدر يجيب اسهم"
        send(msg)

except Exception as e:
    send(f"❌ خطأ في التست: {e}")
