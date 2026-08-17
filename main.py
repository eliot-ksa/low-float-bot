import os, requests, pytz, time
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

playbook = {}
entries = {}
sent = set()
candidates = []
playbook_date = ""

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    except: pass

# --- الفلاتر العشرة ---
def get_ticker_details(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json().get('results',{})
        return {
            'float': r.get('share_class_shares_outstanding', 0),
            'mc': r.get('market_cap', 0)
        }
    except: return {'float':0, 'mc':0}

def get_prev_day(sym):
    try:
        y = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yy = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/day/{yy}/{y}?apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results', [])
        if len(bars) >= 2:
            prev = bars[-1]
            change = (prev['c'] - prev['o'])/prev['o']*100 if prev['o'] else 0
            return change, prev['v']
        return 0, 0
    except: return 0, 0

def check_news_today(sym):
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={sym}&limit=3&apiKey={POLYGON_KEY}"
        news = requests.get(url, timeout=10).json().get('results', [])
        if not news: return False
        # خبر اليوم فقط
        today = datetime.now().strftime('%Y-%m-%d')
        for n in news:
            if today in n.get('published_utc',''): return True
        return False # خبر قديم
    except: return True

def get_spread(sym):
    try:
        url = f"https://api.polygon.io/v3/quotes/{sym}?limit=1&apiKey={POLYGON_KEY}"
        q = requests.get(url, timeout=8).json().get('results',[])
        if q:
            bid = q[0].get('bid_price',0)
            ask = q[0].get('ask_price',0)
            if bid and ask:
                return (ask-bid)/bid*100
        return 0
    except: return 0

def get_indicators(sym):
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{yesterday}/{today}?adjusted=true&sort=desc&limit=100&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=15).json().get('results', [])
        if len(bars) < 30: return None
        bars = list(reversed(bars))
        last_50 = bars[-50:]
        pv = sum(b['c']*b['v'] for b in last_50)
        vv = sum(b['v'] for b in last_50)
        vwap = pv/vv if vv else last_50[-1]['c']
        hod = max(b['h'] for b in last_50)
        closes = [b['c'] for b in bars[-15:]]
        gains = [max(0, closes[i]-closes[i-1]) for i in range(1,len(closes))]
        losses = [max(0, closes[i-1]-closes[i]) for i in range(1,len(closes))]
        avg_gain = sum(gains)/14
        avg_loss = sum(losses)/14 or 0.001
        rsi = 100 - (100/(1+avg_gain/avg_loss))
        # EMA 9/20
        def ema(data, p):
            k = 2/(p+1)
            e = data[0]
            for v in data[1:]: e = v*k + e*(1-k)
            return e
        ema9 = ema([b['c'] for b in bars[-9:]], 9)
        ema20 = ema([b['c'] for b in bars[-20:]], 20)
        last = bars[-1]
        avg_vol = sum(b['v'] for b in bars[-21:-1])/20
        return {
            'price': last['c'], 'vwap': vwap, 'hod': hod,
            'rsi': rsi, 'ema9': ema9, 'ema20': ema20,
            'last_vol': last['v'], 'avg_vol': avg_vol or 1,
            'day_vol': sum(b['v'] for b in last_50)
        }
    except: return None

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        return requests.get(url, timeout=15).json().get('tickers', [])
    except: return []

send("✅ *V10 - 10 فلاتر اشتغل*\n1.Price 2.Float 3.Rotation 4.MCap 5.NewsToday 6.Gap 7.Spread 8.Halt 9.PrevDay 10.Pattern\n11ص-3فجر كل 5د")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)
        hour = now.hour
        today_str = str(now.date())
        active = (11 <= hour <= 23) or (0 <= hour < 3)
        if not active:
            time.sleep(60); continue

        # 1. تجميع 11-4:30 مع 10 فلاتر
        if 11 <= hour < 16 or (hour==16 and now.minute < 30):
            for t in get_gainers()[:50]:
                sym = t.get('ticker','')
                if not sym or len(sym)>5 or any(c['sym']==sym for c in candidates): continue
                day = t.get('day',{})
                price = day.get('c',0)
                change = t.get('todaysChangePerc',0)
                vol = day.get('v',0)

                # فلتر 1+6: السعر والجاب
                if not (1.5 <= price <= 10): continue
                if not (10 <= change <= 90): continue
                # فلتر 8: Halt - اذا طار فوق 120% غالبا halt
                if change > 120: continue

                details = get_ticker_details(sym)
                flt = details['float']
                mc = details['mc']

                # فلتر 2: Float
                if flt!=0 and flt > 10_000_000: continue
                # فلتر 4: Market Cap
                if mc!=0 and mc > 300_000_000: continue
                if flt!=0 and price*flt > 300_000_000: continue

                # فلتر 3: Rotation
                if flt!=0 and vol/flt < 1.2: continue
                # فلتر 3b: Volume vs 30d (تقريبي: لازم >500k)
                if vol < 500_000: continue

                # فلتر 9: Previous Day
                prev_change, prev_vol = get_prev_day(sym)
                if prev_change > 70: continue # طار امس لا تدخل

                # فلتر 5: News Today فقط
                if not check_news_today(sym): continue

                # فلتر 7: Spread
                spr = get_spread(sym)
                if spr > 2.5: continue

                # فلتر 10: Pattern Day 1
                # اذا فوليوم امس عالي معناته Day2
                if prev_vol > vol*0.8 and prev_change > 20: continue

                candidates.append({'sym': sym, 'price': price, 'change': change, 'float': flt, 'mc': mc, 'vol': vol})
                send(f"🔍 *{sym}* ${price:.2f} +{change:.1f}% | F{flt/1e6:.1f}M MC{mc/1e6:.0f}M V{vol/1e6:.1f}M R{vol/(flt or 1):.1f}x")
                time.sleep(1.2)

        # 2. PlayBook 4:30
        if hour==16 and 30 <= now.minute < 35 and playbook_date!= today_str:
            sent.clear(); entries.clear()
            if candidates:
                top = sorted(candidates, key=lambda x: (x['change'], x['vol']), reverse=True)[:3]
                playbook = {c['sym']: c for c in top}
                msg = f"📘 *PlayBook V10 {now.strftime('%m/%d')} - 10 فلاتر*\n\n"
                for i,c in enumerate(top,1):
                    msg+=f"{i}. *{c['sym']}* ${c['price']:.2f} +{c['change']:.1f}% F{c['float']/1e6:.1f}M\n"
                send(msg)
            else:
                send("📭 اليوم لا يوجد - 10 فلاتر صارمة")
            playbook_date = today_str

        # 3. دخول/خروج
        if playbook and (hour>16 or (hour==16 and now.minute>=35) or hour<3 or hour>=17):
            for sym in list(playbook.keys()):
                ind = get_indicators(sym)
                if not ind: continue
                price = ind['price']
                if sym not in entries:
                    # Pattern + EMA + VWAP
                    cond1 = price > ind['hod']*1.003 and ind['last_vol'] > ind['avg_vol']*2 and ind['rsi'] < 75 and ind['ema9'] > ind['ema20']
                    near = abs(price-ind['vwap'])/ind['vwap']*100 < 1.5
                    cond2 = near and price > ind['vwap'] and 45 < ind['rsi'] < 68 and ind['ema9'] > ind['ema20']
                    if cond1 and f"b_{sym}" not in sent:
                        entries[sym]=price
                        send(f"🚀 *{sym} كسر قمة* ${price:.2f} HOD ${ind['hod']:.2f} RSI{ind['rsi']:.0f} EMA9>20 Vol{ind['last_vol']/ind['avg_vol']:.1f}x وقف ${price*0.95:.2f}")
                        sent.add(f"b_{sym}")
                    elif cond2 and f"v_{sym}" not in sent:
                        entries[sym]=price
                        send(f"🟢 *{sym} VWAP+EMA* ${price:.2f} VWAP ${ind['vwap']:.2f} RSI{ind['rsi']:.0f}")
                        sent.add(f"v_{sym}")
                else:
                    entry = entries[sym]
                    profit = (price-entry)/entry*100
                    if profit >= 25 and f"h_{sym}" not in sent:
                        send(f"💰 *نصف {sym} +{profit:.1f}%*")
                        sent.add(f"h_{sym}")
                    if profit >= 50 and f"f_{sym}" not in sent:
                        send(f"🔥 *75% {sym} +{profit:.1f}%*")
                        sent.add(f"f_{sym}")
                    if profit <= -5 and f"s_{sym}" not in sent:
                        send(f"⛔ *وقف {sym} {profit:.1f}%*")
                        sent.add(f"s_{sym}"); del entries[sym]

        if hour==3 and 5 <= now.minute < 10:
            candidates.clear(); playbook.clear(); entries.clear(); sent.clear(); playbook_date=""
            send("🌙 تصفير V10")

        time.sleep(300)
    except Exception as e:
        print(e); time.sleep(60)
