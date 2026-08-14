import os, time, requests, pytz
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

daily_candidates = []
playbook = {}
sent_events = set()
playbook_date = ""

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    except: pass

def get_float(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json()
        f = r.get('results', {}).get('share_class_shares_outstanding', 0)
        return f
    except: return 0

def has_news(sym):
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={sym}&limit=3&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10).json()
        news = r.get('results', [])
        if not news: return False
        # خبر خلال 3 ايام
        for n in news:
            published = n.get('published_utc','')[:10]
            if published:
                d = datetime.strptime(published, '%Y-%m-%d').date()
                if (datetime.now().date() - d).days <= 3:
                    return True
        return False
    except: return True # اذا فشل نعتبر فيه خبر عشان ما نحذف

def get_vwap(sym):
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{yesterday}/{today}?adjusted=true&sort=desc&limit=50&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results', [])
        if len(bars) < 10: return None
        pv = sum(b['c']*b['v'] for b in bars)
        vv = sum(b['v'] for b in bars)
        vwap = pv/vv if vv else bars[0]['c']
        hod = max(b['h'] for b in bars[:30]) # اعلى سعر اليوم
        return {'vwap': vwap, 'last': bars[0]['c'], 'prev': bars[1]['c'], 'hod': hod, 'last_vol': bars[0]['v'], 'prev_vol': bars[1]['v'] or 1, 'low': min(b['l'] for b in bars[:30])}
    except: return None

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        return requests.get(url, timeout=15).json().get('tickers', [])
    except: return []

send("✅ *V8 PlayBookTrades الاصلي اشتغل*\nFloat<10M + سعر 1.5-10$ + خبر\nالتجميع 11ص-4:30م\nالدخول بعد الافتتاح فقط\nاشارات: VWAP + كسر قمة")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)
        today_str = str(now.date())

        # 1. تجميع بري ماركت 11ص الى 4:30م
        if 11 <= now.hour < 16 or (now.hour == 16 and now.minute < 30):
            if len(daily_candidates) < 20:
                for t in get_gainers()[:40]:
                    sym = t.get('ticker','')
                    if not sym or len(sym)>5 or any(c['sym']==sym for c in daily_candidates): continue
                    price = t.get('day',{}).get('c',0)
                    change = t.get('todaysChangePerc',0)
                    vol = t.get('day',{}).get('v',0)

                    # فلتر PlayBookTrades الاصلي
                    if not (1.5 <= price <= 10 and 10 <= change <= 80 and vol > 300000):
                        continue

                    f = get_float(sym)
                    if f == 0 or f > 10000000: # Float لازم اقل من 10M
                        continue

                    if not has_news(sym):
                        continue

                    daily_candidates.append({'sym': sym, 'price': price, 'change': change, 'vol': vol, 'float': f, 'score': change + (10 if f < 5000000 else 0)})
                    send(f"🔍 PlayBook مرشح: *{sym}* ${price:.2f} +{change:.1f}% Float {f/1000000:.1f}M 📰")
                    time.sleep(1.2)

        # 2. بناء PlayBook الساعة 4:30م (افتتاح السوق)
        if now.hour == 16 and now.minute == 30 and playbook_date!= today_str:
            if not daily_candidates:
                send("📭 اليوم ما فيه اسهم بمواصفات PlayBookTrades - لا تداول")
            else:
                top = sorted(daily_candidates, key=lambda x: x['score'], reverse=True)[:2] # يختار 2 فقط مثل الاصلي
                playbook = {c['sym']: {'entry': 0, 'hod': c['price']} for c in top}
                msg = f"📘 *PlayBookTrades اليوم {now.strftime('%m/%d')}*\nفحصنا {len(daily_candidates)} سهم بمواصفات Float<10M\n\n"
                for i,c in enumerate(top,1):
                    msg+=f"{i}. *{c['sym']}* ${c['price']:.2f} +{c['change']:.1f}% Float {c['float']/1000000:.1f}M\n"
                msg+="\n⏳ *ما تدخل قبل 4:35م* - ننتظر تثبيت فوق VWAP\nالاشارات: كسر قمة + ارتداد VWAP"
                send(msg)
            playbook_date = today_str

        # 3. اشارات دخول بعد الافتتاح فقط (4:35م - 11م)
        if playbook and (now.hour > 16 or (now.hour==16 and now.minute>=35)):
            for t in get_gainers()[:50]:
                sym = t.get('ticker')
                if sym not in playbook: continue
                price = t.get('day',{}).get('c',0)
                vd = get_vwap(sym)
                if not vd: continue

                # اشارة 1: كسر قمة اليوم
                if price > vd['hod'] * 1.001 and vd['last_vol'] > vd['prev_vol']*1.5:
                    key = f"break_{sym}"
                    if key not in sent_events:
                        playbook[sym]['entry'] = price
                        send(f"🚀 *كسر قمة {sym} - دخول PlayBookTrades*\nقمة سابقة ${vd['hod']:.2f} | كسر ${price:.2f}\nفوليوم {vd['last_vol']/vd['prev_vol']:.1f}x\nوقف: تحت ${vd['low']:.2f}\n[📈 الشارت](https://www.tradingview.com/chart/?symbol={sym})")
                        sent_events.add(key)

                # اشارة 2: ارتداد VWAP
                diff = ((vd['last'] - vd['vwap'])/vd['vwap']*100)
                if -1.5 <= diff <= 1.5 and vd['last'] > vd['prev'] and vd['last_vol'] > vd['prev_vol']*1.3:
                    key = f"vwap_{sym}_{now.strftime('%H%M')}"
                    if key not in sent_events and f"break_{sym}" not in sent_events: # اذا ما دخل كسر قمة
                        playbook[sym]['entry'] = price
                        send(f"🟢 *ارتداد VWAP {sym} - دخول*\nVWAP ${vd['vwap']:.2f} | لمس ${vd['last']:.2f}\nوقف تحت VWAP 2%\n[📈 الشارت](https://www.tradingview.com/chart/?symbol={sym})")
                        sent_events.add(key)

                # خروج
                entry = playbook[sym]['entry']
                if entry:
                    profit = ((price-entry)/entry*100)
                    if profit >= 25 and f"half_{sym}" not in sent_events:
                        send(f"💰 *بيع نصف {sym}* +{profit:.1f}% - حط الوقف على الدخول")
                        sent_events.add(f"half_{sym}")
                    if profit <= -5 and f"stop_{sym}" not in sent_events:
                        send(f"⛔ *وقف {sym}* {profit:.1f}% - اطلع")
                        sent_events.add(f"stop_{sym}")

        # تصفير يوم جديد 3ص
        if now.hour == 3 and now.minute < 5:
            daily_candidates.clear()
            playbook.clear()
            sent_events.clear()

        time.sleep(40)

    except Exception as e:
        print(e)
        time.sleep(20)
