import os, requests, pytz, time
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

playbook = {}
entries = {} # sym -> entry price
sent = set()
candidates = []
playbook_date = ""

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    except: pass

def get_float(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json()
        return r.get('results',{}).get('share_class_shares_outstanding', 0)
    except: return 0

def has_news(sym):
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={sym}&limit=2&apiKey={POLYGON_KEY}"
        return len(requests.get(url, timeout=10).json().get('results', [])) > 0
    except: return True

def get_indicators(sym):
    try:
        # اخر 50 شمعة دقيقة
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{yesterday}/{today}?adjusted=true&sort=desc&limit=100&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=15).json().get('results', [])
        if len(bars) < 20: return None

        # VWAP
        pv = sum(b['c']*b['v'] for b in bars[:50])
        vv = sum(b['v'] for b in bars[:50])
        vwap = pv/vv if vv else bars[0]['c']

        # HOD / LOD
        hod = max(b['h'] for b in bars[:50])
        lod = min(b['l'] for b in bars[:50])

        # RSI مبسط 14
        closes = [b['c'] for b in bars[:15]][::-1]
        gains = sum(max(0, closes[i]-closes[i-1]) for i in range(1,len(closes)))
        losses = sum(max(0, closes[i-1]-closes[i]) for i in range(1,len(closes)))
        rs = gains/(losses or 0.001)
        rsi = 100 - (100/(1+rs))

        # Volume
        last_vol = bars[0]['v']
        avg_vol = sum(b['v'] for b in bars[1:21])/20

        return {
            'price': bars[0]['c'],
            'vwap': vwap,
            'hod': hod,
            'lod': lod,
            'rsi': rsi,
            'last_vol': last_vol,
            'avg_vol': avg_vol or 1,
            'prev_close': bars[1]['c']
        }
    except: return None

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        return requests.get(url, timeout=15).json().get('tickers', [])
    except: return []

send("✅ *V9 اشتغل - 11ص الى 3 الفجر*\nتحديث كل 5 دقايق\nفلتر: 1.5-10$ + Float<10M + خبر\nدخول: كسر قمة + VWAP + RSI\nخروج: 25%/50% + وقف 5%")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)
        hour = now.hour
        today_str = str(now.date())

        # الوقت: 11ص الى 3 الفجر (11-23 و 0-3)
        active_time = (11 <= hour <= 23) or (0 <= hour < 3)
        if not active_time:
            time.sleep(60)
            continue

        # 1. تجميع 11ص - 4:30م
        if 11 <= hour < 16 or (hour==16 and now.minute < 30):
            for t in get_gainers()[:40]:
                sym = t.get('ticker','')
                if not sym or len(sym)>5 or any(c['sym']==sym for c in candidates): continue
                price = t.get('day',{}).get('c',0)
                change = t.get('todaysChangePerc',0)
                if not (1.5 <= price <= 10 and 10 <= change <= 120): continue

                f = get_float(sym)
                if f!=0 and f > 10000000: continue
                if not has_news(sym): continue

                candidates.append({'sym': sym, 'price': price, 'change': change})
                send(f"🔍 مرشح: *{sym}* ${price:.2f} +{change:.1f}% Float {f/1000000:.1f}M" if f else f"🔍 مرشح: *{sym}* ${price:.2f} +{change:.1f}%")
                time.sleep(1)

        # 2. بناء PlayBook 4:30م
        if hour==16 and now.minute>=30 and now.minute<35 and playbook_date!= today_str:
            if candidates:
                top = sorted(candidates, key=lambda x: x['change'], reverse=True)[:3]
                playbook = {c['sym']: c for c in top}
                msg = f"📘 *PlayBook {now.strftime('%m/%d')} - 11ص الى 3 الفجر*\n\n"
                for i,c in enumerate(top,1):
                    msg+=f"{i}. *{c['sym']}* ${c['price']:.2f} +{c['change']:.1f}%\n"
                msg+="\n⏰ المراقبة كل 5 دقايق الى 3 الفجر\nدخول بعد 4:35م فقط"
                send(msg)
                playbook_date = today_str
            else:
                send("📭 اليوم ما فيه اسهم مطابقة - نكمل مراقبة الى 3 الفجر")
                playbook_date = today_str

        # 3. مراقبة ودخول/خروج كل 5 دقايق (4:35م - 3 الفجر)
        if playbook and (hour>16 or (hour==16 and now.minute>=35) or hour<3 or hour>=17):
            for sym in list(playbook.keys()):
                ind = get_indicators(sym)
                if not ind: continue
                price = ind['price']

                # --- دخول ---
                if sym not in entries:
                    # شرط 1: كسر قمة بفوليوم + RSI <70
                    cond_break = price > ind['hod']*1.002 and ind['last_vol'] > ind['avg_vol']*1.8 and ind['rsi'] < 72
                    # شرط 2: ارتداد VWAP + RSI 40-60
                    near_vwap = abs(price - ind['vwap'])/ind['vwap']*100 < 1.2
                    cond_vwap = near_vwap and price > ind['prev_close'] and 40 < ind['rsi'] < 65 and ind['last_vol'] > ind['avg_vol']*1.3

                    if cond_break and f"break_{sym}" not in sent:
                        entries[sym] = price
                        send(f"🚀 *دخول كسر قمة {sym}*\nسعر ${price:.2f} | قمة ${ind['hod']:.2f}\nRSI {ind['rsi']:.0f} | Vol {ind['last_vol']/ind['avg_vol']:.1f}x\nVWAP ${ind['vwap']:.2f}\nوقف: ${ind['lod']:.2f} (-5%)\n[📈 شارت](https://www.tradingview.com/chart/?symbol={sym})")
                        sent.add(f"break_{sym}")

                    elif cond_vwap and f"vwap_{sym}" not in sent:
                        entries[sym] = price
                        send(f"🟢 *دخول ارتداد VWAP {sym}*\nسعر ${price:.2f} | VWAP ${ind['vwap']:.2f}\nRSI {ind['rsi']:.0f} | Vol {ind['last_vol']/ind['avg_vol']:.1f}x\nوقف تحت VWAP 2%\n[📈 شارت](https://www.tradingview.com/chart/?symbol={sym})")
                        sent.add(f"vwap_{sym}")

                # --- خروج ---
                else:
                    entry = entries[sym]
                    profit = (price-entry)/entry*100

                    # هدف 1: 25%
                    if profit >= 25 and f"half_{sym}" not in sent:
                        send(f"💰 *بيع نصف {sym} +{profit:.1f}%*\nدخول ${entry:.2f} -> ${price:.2f}\nحرك الوقف على الدخول")
                        sent.add(f"half_{sym}")

                    # هدف 2: 50%
                    if profit >= 50 and f"full_{sym}" not in sent:
                        send(f"🔥 *بيع 75% {sym} +{profit:.1f}%*\nخل ربع اخير مجاني")
                        sent.add(f"full_{sym}")

                    # وقف خسارة 5% او كسر VWAP ب 3%
                    if profit <= -5 or price < ind['vwap']*0.97:
                        if f"stop_{sym}" not in sent:
                            send(f"⛔ *وقف {sym} {profit:.1f}%*\nسعر ${price:.2f} | VWAP ${ind['vwap']:.2f}\nRSI {ind['rsi']:.0f}")
                            sent.add(f"stop_{sym}")
                            del entries[sym] # اطلع من السهم

                    # تنبيه RSI عالي جدا (تشبع)
                    if ind['rsi'] > 82 and f"rsi_{sym}" not in sent:
                        send(f"⚠️ *{sym} تشبع RSI {ind['rsi']:.0f}* - فكر تبيع")
                        sent.add(f"rsi_{sym}")

        # تصفير يوم جديد 3:05 الفجر
        if hour==3 and now.minute>=5 and now.minute<10:
            candidates.clear()
            playbook.clear()
            entries.clear()
            sent.clear()
            send("🌙 انتهت جلسة اليوم - تصفير للبكرة 11ص")

        # تحديث كل 5 دقايق
        time.sleep(300)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)
