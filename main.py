import os, time, requests, pytz
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

sent = set()

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    except: pass

def is_allowed():
    h = datetime.now(pytz.timezone('Asia/Riyadh')).hour
    return not (3 <= h < 11) # 11ص لـ 3ص

def get_float(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json()
        return r.get('results', {}).get('share_class_shares_outstanding', 0)
    except: return 0

def analyze_entry(sym):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{(datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?adjusted=true&sort=desc&limit=30&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results', [])
        if len(bars) < 10: return "⚠️ بيانات قليلة"

        pv = sum(b['c']*b['v'] for b in bars)
        vv = sum(b['v'] for b in bars)
        vwap = pv/vv if vv else bars[0]['c']
        last = bars[0]['c']
        avg_vol = sum([b['v'] for b in bars[1:10]])/9
        rel_vol = bars[0]['v']/avg_vol if avg_vol else 0
        diff = ((last - vwap)/vwap*100)

        score = 0
        reasons = []

        if -3 <= diff <= 3:
            score+=2; reasons.append("✅ عند VWAP (افضل دخول)")
        elif 3 < diff <= 8:
            score+=1; reasons.append(f"⚠️ فوق VWAP {diff:.1f}%")
        elif diff > 8:
            score-=2; reasons.append(f"⛔ بعيد فوق VWAP {diff:.1f}% - خطر قمة")
        else:
            reasons.append(f"📉 تحت VWAP {diff:.1f}% - انتظر")

        if rel_vol > 2:
            score+=2; reasons.append(f"🔥 فوليوم قوي {rel_vol:.1f}x")
        elif rel_vol > 1.2:
            score+=1; reasons.append(f"فوليوم جيد {rel_vol:.1f}x")
        else:
            score-=1; reasons.append(f"فوليوم ضعيف {rel_vol:.1f}x")

        if score >= 3: dec = "🟢 *القرار: ادخل*"
        elif score >= 1: dec = "🟡 *القرار: نصف كمية*"
        else: dec = "🔴 *القرار: تجنب*"

        return dec + "\n" + "\n".join(reasons) + f"\nVWAP: ${vwap:.2f}"
    except:
        return "تحليل غير متوفر"

def scan():
    alerts = []
    try:
        gainers = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}", timeout=15).json().get('tickers', [])[:20]
        for t in gainers:
            sym = t.get('ticker')
            if not sym or len(sym)>5 or sym in sent: continue
            price = t.get('day',{}).get('c',0)
            vol = t.get('day',{}).get('v',0)
            change = t.get('todaysChangePerc',0)
            if not (1.5 < price < 8 and change > 10 and vol > 300000): continue
            f = get_float(sym)
            if f > 15000000: continue
            ftxt = f"{f/1000000:.1f}M" if f else "?"
            analysis = analyze_entry(sym)
            msg = f"🎯 *{sym}* - ${price:.2f} (+{change:.1f}%)\nFloat: {ftxt} Vol: {vol/1000:.0f}K\n\n{analysis}\n\n[📈 الشارت](https://www.tradingview.com/chart/?symbol={sym})"
            alerts.append(msg)
            sent.add(sym)
            time.sleep(1.2)
    except Exception as e:
        print(e)
    return alerts

send("✅ *البوت V4 اشتغل*\n11ص-3ص بتوقيت الرياض\nمع قرار دخول + فحص VWAP")
print("V4 Started")

last_day = ""
while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)
        if not is_allowed():
            if now.hour == 3 and now.minute < 2: sent.clear()
            print("نايم"); time.sleep(60); continue
        if now.hour == 11 and now.minute == 5 and str(now.date())!=last_day:
            send(f"📘 *خطة اليوم {now.strftime('%m/%d')}*\nمراقبة: Float <15M +10%\nالدخول فقط اذا 🟢")
            last_day = str(now.date())
        print(f"🔍 {now.strftime('%H:%M:%S')}")
        for m in scan(): send(m)
        time.sleep(60)
    except Exception as e:
        print(e); time.sleep(15)
