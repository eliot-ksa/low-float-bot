import os, time, requests, pytz
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

daily_candidates = [] # يجمع طول اليوم
daily_top3 = [] # افضل 3
sent_rocket = set()
playbook_sent_date = ""

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    except: pass

def is_allowed():
    h = datetime.now(pytz.timezone('Asia/Riyadh')).hour
    return not (3 <= h < 11)

def get_float(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json()
        return r.get('results', {}).get('share_class_shares_outstanding', 0)
    except: return 0

def get_score(sym, price, change, vol):
    """يعطي نقاط - كل ما قل Float وارتفع الفوليوم كل ما كانت النقاط اعلى"""
    try:
        float_shares = get_float(sym)
        if float_shares > 12000000: return -1, 0, "Float كبير"

        # نقاط
        score = 0
        score += min(change * 2, 40) # كل 1% = نقطتين
        score += min(vol / 100000, 20) # كل 100k = نقطة
        if float_shares < 5000000: score += 30
        elif float_shares < 10000000: score += 15

        # VWAP
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{(datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?adjusted=true&sort=desc&limit=20&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results', [])
        if bars:
            pv = sum(b['c']*b['v'] for b in bars)
            vv = sum(b['v'] for b in bars)
            vwap = pv/vv if vv else price
            diff = abs(price - vwap)/vwap*100
            if diff <= 3: score += 20 # عند VWAP

        return score, float_shares, f"{float_shares/1000000:.1f}M" if float_shares else "?"
    except:
        return 0, 0, "?"

def build_playbook():
    global daily_top3
    if not daily_candidates: return

    # رتب حسب النقاط وخذ افضل 3
    sorted_cands = sorted(daily_candidates, key=lambda x: x['score'], reverse=True)[:3]
    daily_top3 = [c['sym'] for c in sorted_cands]

    msg = f"📘 *PLAYBOOK اليوم {datetime.now(pytz.timezone('Asia/Riyadh')).strftime('%m/%d')}*\n"
    msg += f"فحصنا {len(daily_candidates)} سهم مرشح - اخترنا افضل 3:\n\n"

    for i, c in enumerate(sorted_cands, 1):
        msg += f"{i}. *{c['sym']}* - ${c['price']:.2f} (+{c['change']:.1f}%)\n"
        msg += f"   Float: {c['float_txt']} Vol: {c['vol']/1000:.0f}K Score: {c['score']:.0f}\n"
        msg += f"   خطة: انتظار لمس VWAP\n\n"

    msg += "⏰ *التنبيهات الجاية فقط لهذه الـ 3*"
    send(msg)

# بداية
send("✅ *بوت PlayBook V5 اشتغل*\nالنظام: يفحص 1000+ سهم - يختار افضل 3 فقط يوميا\n11ص-11:15ص تجميع - 11:15 يرسل الـ PlayBook")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)

        if not is_allowed():
            if now.hour == 3 and now.minute < 5:
                daily_candidates.clear()
                daily_top3.clear()
                sent_rocket.clear()
            time.sleep(60)
            continue

        # 1. مرحلة التجميع: 11ص الى 11:15ص
        if 11 <= now.hour < 12 and now.minute < 15:
            print(f"📥 تجميع... {now.strftime('%H:%M:%S')}")
            try:
                gainers = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}", timeout=15).json().get('tickers', [])[:40]
                for t in gainers:
                    sym = t.get('ticker')
                    if not sym or len(sym)>5: continue
                    if any(c['sym']==sym for c in daily_candidates): continue

                    price = t.get('day',{}).get('c',0)
                    vol = t.get('day',{}).get('v',0)
                    change = t.get('todaysChangePerc',0)

                    if not (1.5 < price < 8 and 10 <= change < 60 and vol > 250000): continue

                    score, fshares, ftxt = get_score(sym, price, change, vol)
                    if score < 20: continue

                    daily_candidates.append({
                        'sym': sym, 'price': price, 'change': change,
                        'vol': vol, 'score': score, 'float_txt': ftxt
                    })
                    print(f"Added {sym} score {score}")
                    time.sleep(1)
            except Exception as e:
                print(e)

        # 2. ارسل PlayBook الساعة 11:15
        if now.hour == 11 and now.minute == 15 and playbook_sent_date != str(now.date()):
            build_playbook()
            playbook_sent_date = str(now.date())

        # 3. بعد الـ PlayBook - تابع الـ 3 فقط اذا قربوا 50%
        if daily_top3 and (now.hour > 11 or (now.hour==11 and now.minute>=15)):
            try:
                gainers = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}", timeout=15).json().get('tickers', [])[:50]
                for t in gainers:
                    sym = t.get('ticker')
                    if sym not in daily_top3 or sym in sent_rocket: continue

                    price = t.get('day',{}).get('c',0)
                    change = t.get('todaysChangePerc',0)
                    vol = t.get('day',{}).get('v',0)

                    if change >= 30:
                        send(f"🚀 *{sym} من الـ PlayBook يقترب من 50%*\nالان: ${price:.2f} (+{change:.1f}%) Vol {vol/1000000:.1f}M\n[الشارت](https://www.tradingview.com/chart/?symbol={sym})")
                        sent_rocket.add(sym)
            except Exception as e:
                print(e)

        time.sleep(60)

    except Exception as e:
        print(e)
        time.sleep(15)
