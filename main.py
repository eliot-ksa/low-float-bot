import os, time, requests, schedule, pytz
from datetime import datetime, timedelta

# اساميك انتي اللي في الصورة
POLYGON_KEY = os.getenv("POLYGON_KEY", "")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("CHAT_ID", "")

KSA = pytz.timezone('Asia/Riyadh')

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(f"No telegram keys")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        print("Telegram sent ✅")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        return requests.get(url, timeout=15).json().get('tickers', [])
    except Exception as e:
        print(f"Gainers error: {e}")
        return []

def get_details(sym):
    try:
        snap = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=15).json()
        ticker = snap.get('ticker',{})
        day = ticker.get('day',{})
        prev = ticker.get('prevDay',{})
        price = day.get('c',0)
        if price == 0: return None
        change = ((price - prev.get('c',1)) / prev.get('c',1) * 100) if prev.get('c') else 0
        vol = day.get('v',0)
        
        hist = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/day/{(datetime.now()-timedelta(days=100)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?apiKey={POLYGON_KEY}", timeout=15).json()
        results = hist.get('results',[])
        if len(results) < 25: return None
        closes = [b['c'] for b in results]
        vols = [b['v'] for b in results]
        
        avg_vol = sum(vols[-20:-1]) / 19 if len(vols)>20 else 0
        rel_vol = vol / avg_vol if avg_vol else 0
        sma20 = sum(closes[-20:]) / 20
        sma50 = sum(closes[-50:]) / 50 if len(closes)>=50 else sma20*0.9
        high_90 = max(closes[-90:]) if len(closes)>=90 else max(closes)
        low_90 = min(closes[-90:]) if len(closes)>=90 else min(closes)
        box_range = (high_90 - low_90) / low_90 if low_90 else 1
        vwap = day.get('vw', price)
        
        return {
            'sym': sym, 'price': price, 'change': change, 'vol': vol,
            'rel_vol': rel_vol, 'avg_vol': avg_vol,
            'sma20': sma20, 'sma50': sma50,
            'high_90': high_90, 'low_90': low_90, 'box_range': box_range,
            'vwap': vwap
        }
    except:
        return None

def scan():
    gainers = get_gainers()
    picks = []
    for t in gainers[:50]:
        sym = t.get('ticker')
        if not sym: continue
        d = get_details(sym)
        if not d: continue
        if not (10 <= d['change'] <= 150): continue
        if d['price'] < d['sma20']: continue
        if not (d['sma50'] < d['sma20']): continue
        if d['avg_vol'] < 300_000: continue
        if d['rel_vol'] < 2.0: continue
        if d['vol'] < 1_000_000: continue
        if d['price'] < 1 or d['price'] > 25: continue
        if d['box_range'] > 0.50: continue
        score = d['rel_vol'] + (d['change']/20)
        if d['price'] > d['high_90']*0.98: score+=2
        d['score'] = score
        picks.append(d)
    return sorted(picks, key=lambda x: x['score'], reverse=True)[:3]

def job():
    try:
        now_ksa = datetime.now(KSA)
        hour = now_ksa.hour
        if 3 <= hour < 11:
            print(f"{now_ksa.strftime('%H:%M')} KSA - نايم")
            return
        print(f"{now_ksa.strftime('%H:%M')} KSA - يفحص السوق...")
        picks = scan()
        if not picks:
            print("No picks")
            return
        for p in picks:
            msg = f"""
🚀 *V11 PICK - {p['sym']}*
💰 ${p['price']:.2f} | 📈 +{p['change']:.1f}%
🔥 RelVol: {p['rel_vol']:.1f}x | 📦 {p['vol']/1_000_000:.1f}M
🎯 بوكس: {p['low_90']:.2f} - {p['high_90']:.2f}$
*دخول:* فوق ${p['vwap']:.2f}
*وقف:* ${p['low_90']:.2f}
*وقت:* {now_ksa.strftime('%H:%M')} KSA
"""
            send_telegram(msg)
            time.sleep(1)
    except Exception as e:
        print(f"Job error: {e}")

print("V11 Bot Starting...")
send_telegram(f"✅ *V11 اشتغل*\n⏰ من 11 الصبح الى 3 الفجر KSA\n📅 {datetime.now(KSA).strftime('%H:%M')} KSA")

schedule.every(5).minutes.do(job)
job()

while True:
    try:
        schedule.run_pending()
        time.sleep(30)
    except Exception as e:
        print(f"Loop error: {e}")
        time.sleep(60)
