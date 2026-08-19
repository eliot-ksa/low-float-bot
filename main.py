import requests, json, time, schedule
from datetime import datetime, timedelta

# ========== حطي مفاتيحك هنا ==========
POLYGON_KEY = "ضع_مفتاح_polygon_هنا"
TELEGRAM_TOKEN = "ضع_توكن_البوت_هنا"
TELEGRAM_CHAT = "ضع_الشات_ID_هنا"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except: pass

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        return requests.get(url, timeout=10).json().get('tickers', [])
    except:
        return []

def get_details(sym):
    try:
        snap = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json()
        ticker = snap.get('ticker',{})
        day = ticker.get('day',{})
        prev = ticker.get('prevDay',{})
        
        price = day.get('c',0)
        if price == 0: return None
        change = ((price - prev.get('c',1)) / prev.get('c',1) * 100) if prev.get('c') else 0
        vol = day.get('v',0)
        
        hist = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/day/{(datetime.now()-timedelta(days=100)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?apiKey={POLYGON_KEY}", timeout=10).json()
        results = hist.get('results',[])
        if len(results) < 25: return None
        
        closes = [b['c'] for b in results]
        vols = [b['v'] for b in results]
        
        avg_vol = sum(vols[-20:-1]) / 19
        rel_vol = vol / avg_vol if avg_vol else 0
        sma20 = sum(closes[-20:]) / 20
        sma50 = sum(closes[-50:]) / 50 if len(closes)>=50 else sma20*0.9
        high_90 = max(closes[-90:]) if len(closes)>=90 else max(closes)
        low_90 = min(closes[-90:]) if len(closes)>=90 else min(closes)
        box_range = (high_90 - low_90) / low_90 if low_90 else 1
        ema9 = sum(closes[-9:]) / 9
        vwap = day.get('vw', price)
        
        return {
            'sym': sym, 'price': price, 'change': change, 'vol': vol,
            'rel_vol': rel_vol, 'avg_vol': avg_vol,
            'sma20': sma20, 'sma50': sma50,
            'high_90': high_90, 'low_90': low_90, 'box_range': box_range,
            'ema9': ema9, 'vwap': vwap
        }
    except:
        return None

def scan():
    gainers = get_gainers()
    picks = []
    for t in gainers[:50]: # اول 50 سهم طاير
        sym = t.get('ticker')
        if not sym: continue
        d = get_details(sym)
        if not d: continue
        
        # فلتر الفيديو
        if not (10 <= d['change'] <= 150): continue
        if d['price'] < d['sma20']: continue
        if not (d['sma50'] < d['sma20']): continue
        if d['avg_vol'] < 300_000: continue
        if d['rel_vol'] < 2.0: continue
        if d['vol'] < 1_000_000: continue
        
        # حماية V10
        if d['price'] < 1 or d['price'] > 25: continue
        if d['price'] < d['vwap']*0.98: continue
        if d['ema9'] < d['sma20']*0.98: continue
        if d['box_range'] > 0.50: continue
        
        score = d['rel_vol'] + (d['change']/20)
        if d['price'] > d['high_90']*0.98: score+=2
        d['score'] = score
        picks.append(d)
    
    picks = sorted(picks, key=lambda x: x['score'], reverse=True)[:3]
    return picks

def job():
    now = datetime.now()
    hour = now.hour
    
    # يشتغل من 11 الصبح الى 3 الفجر بتوقيت السعودية
    # ينام بس من 3 الى 11 الصبح
    if 3 <= hour < 11:
        print(f"{now.strftime('%H:%M')} - نايم 💤")
        return
    
    print(f"{now.strftime('%H:%M')} - يفحص السوق...")
    picks = scan()
    
    if not picks:
        return
    
    for p in picks:
        msg = f"""
🚀 *V11 PICK - {p['sym']}*

💰 ${p['price']:.2f} | 📈 +{p['change']:.1f}%
🔥 RelVol: {p['rel_vol']:.1f}x | 📦 {p['vol']/1_000_000:.1f}M
📊 SMA20: ${p['sma20']:.2f} | SMA50: ${p['sma50']:.2f}
🎯 بوكس: {p['low_90']:.2f} - {p['high_90']:.2f}$

*دخول:* فوق ${p['vwap']:.2f}
*وقف:* ${p['low_90']:.2f}
*هدف:* +15%
*وقت:* {now.strftime('%H:%M')} KSA
"""
        send_telegram(msg)
        time.sleep(1)

# ========== التشغيل ==========
send_telegram("✅ *V11 اشتغل*\n⏰ من 11 الصبح الى 3 الفجر KSA\n🔍 يشيك كل 5 دقايق")

schedule.every(5).minutes.do(job)
job() # فحص اول مرة

while True:
    schedule.run_pending()
    time.sleep(30)
