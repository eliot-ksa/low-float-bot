import os, requests, pytz, time, csv
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

# === اعدادات 10/10 ===
MAX_RISK_PER_TRADE = 1.0 # 1% مخاطرة
MAX_LOSSES_PER_DAY = 2
MAX_MARKET_CAP = 150_000_000 # 150M
MIN_ROTATION = 1.2
PORTFOLIO = 10000 # محفظتك بالدولار

playbook = {}
entries = {}
sent = set()
candidates = []
playbook_date = ""
daily_losses = 0
trades_log = []

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    except: pass

def log_trade(sym, entry, exit_p, profit, reason):
    try:
        with open('trades.csv','a',newline='') as f:
            csv.writer(f).writerow([datetime.now(), sym, entry, exit_p, f"{profit:.2f}%", reason])
    except: pass

def get_float_mc(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json().get('results',{})
        return r.get('share_class_shares_outstanding',0), r.get('market_cap',0)
    except: return 0,0

def get_prev_day_change(sym):
    try:
        y = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yy = (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/day/{yy}/{y}?apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results', [])
        if len(bars)>=2:
            prev = bars[-1]
            ch = (prev['c']-prev['o'])/prev['o']*100 if prev['o'] else 0
            return ch, prev['v'], prev['c']
        return 0,0,0
    except: return 0,0,0

def get_spy_trend():
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/SPY/range/1/day/{(datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results',[])
        if len(bars)>=2:
            return (bars[-1]['c']-bars[-2]['c'])/bars[-2]['c']*100
        return 0
    except: return 0

def has_news_recent(sym):
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={sym}&limit=2&apiKey={POLYGON_KEY}"
        news = requests.get(url, timeout=10).json().get('results',[])
        if not news: return False
        # خبر خلال 3 ايام
        for n in news:
            pub = n.get('published_utc','')[:10]
            if pub:
                d = datetime.strptime(pub, '%Y-%m-%d')
                if (datetime.now()-d).days <= 3:
                    return True
        return False
    except: return True

def get_indicators(sym):
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{yesterday}/{today}?adjusted=true&sort=desc&limit=150&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=15).json().get('results', [])
        if len(bars) < 30: return None
        bars = list(reversed(bars))
        last_50 = bars[-50:]
        pv = sum(b['c']*b['v'] for b in last_50)
        vv = sum(b['v'] for b in last_50)
        vwap = pv/vv if vv else last_50[-1]['c']
        hod = max(b['h'] for b in last_50)
        lod = min(b['l'] for b in last_50)
        closes = [b['c'] for b in bars[-20:]]
        # RSI
        gains = [max(0, closes[i]-closes[i-1]) for i in range(1,len(closes))]
        losses = [max(0, closes[i-1]-closes[i]) for i in range(1,len(closes))]
        avg_gain = sum(gains[-14:])/14 if len(gains)>=14 else sum(gains)/len(gains) if gains else 0
        avg_loss = sum(losses[-14:])/14 if len(losses)>=14 else sum(losses)/len(losses) if losses else 0.001
        rsi = 100 - (100/(1+avg_gain/(avg_loss or 0.001)))
        # EMA
        def ema(data,p):
            k=2/(p+1); e=data[0]
            for v in data[1:]: e=v*k+e*(1-k)
            return e
        ema9 = ema(closes[-9:],9)
        ema20 = ema(closes[-20:],20)
        last = bars[-1]
        avg_vol = sum(b['v'] for b in bars[-21:-1])/20
        return {
            'price': last['c'], 'vwap': vwap, 'hod': hod, 'lod': lod,
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

send("✅ *V10 ULTIMATE 10/10 اشتغل*\n10 فلاتر + EMA + Risk 1% + تسجيل\n11ص-3فجر كل 5د")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)
        hour = now.hour
        today_str = str(now.date())
        active = (11 <= hour <= 23) or (0 <= hour < 3)
        if not active:
            time.sleep(60); continue

        # === 1. تجميع 11-4:30 بالـ 10 فلاتر ===
        if 11 <= hour < 16 or (hour==16 and now.minute < 30):
            # فحص SPY
            spy = get_spy_trend()
            if spy < -1.0 and hour>=16:
                if f"spy_{today_str}" not in sent:
                    send(f"⚠️ SPY {spy:.1f}% نزول - تداول حذر اليوم")
                    sent.add(f"spy_{today_str}")

            for t in get_gainers()[:60]:
                sym = t.get('ticker','')
                if not sym or len(sym)>5 or any(c['sym']==sym for c in candidates): continue
                day = t.get('day',{})
                price = day.get('c',0)
                change = t.get('todaysChangePerc',0)
                vol = day.get('v',0)

                # 1+6: Price + Gap
                if not (1.5 <= price <= 10): continue
                if not (10 <= change <= 90): continue
                if vol < 300_000: continue

                flt, mc = get_float_mc(sym)
                # 2: Float <15M (خففنا)
                if flt!=0 and flt > 15_000_000: continue
                # 4: Market Cap <150M
                if mc!=0 and mc > MAX_MARKET_CAP: continue
                if flt!=0 and price*flt > MAX_MARKET_CAP: continue
                # 3: Rotation
                if flt!=0 and vol/flt < MIN_ROTATION: continue

                # 9: Prev Day
                prev_ch, prev_vol, prev_close = get_prev_day_change(sym)
                if prev_ch > 70: continue # Day2
                if prev_vol > vol*1.2 and prev_ch > 15: continue

                # 5: News 3 ايام
                if not has_news_recent(sym): continue

                # 10: Pattern Day1
                if price < prev_close*1.05 and prev_ch > 10: continue

                candidates.append({'sym': sym, 'price': price, 'change': change, 'float': flt, 'mc': mc, 'vol': vol, 'prev_ch': prev_ch})
                send(f"🔍 *{sym}* ${price:.2f} +{change:.1f}% F{flt/1e6:.1f}M R{vol/(flt or 1):.1f}x MC{mc/1e6:.0f}M")
                time.sleep(1)

        # === 2. PlayBook 4:30 ===
        if hour==16 and 30 <= now.minute < 35 and playbook_date!= today_str:
            sent = {s for s in sent if s.startswith("spy_")} # احتفظ بتحذير SPY فقط
            entries.clear()
            daily_losses = 0
            if candidates:
                top = sorted(candidates, key=lambda x: (x['vol']/(x['float'] or 1), x['change']), reverse=True)[:3]
                playbook = {c['sym']: c for c in top}
                msg = f"📘 *PlayBook ULTIMATE {now.strftime('%m/%d')}*\nSPY {get_spy_trend():.1f}% | Risk 1%\n\n"
                for i,c in enumerate(top,1):
                    risk_shares = int((PORTFOLIO*0.01)/(c['price']*0.05)) # وقف 5%
                    msg+=f"{i}. *{c['sym']}* ${c['price']:.2f} +{c['change']:.1f}% F{c['float']/1e6:.1f}M R{c['vol']/(c['float'] or 1):.1f}x | {risk_shares} سهم\n"
                send(msg)
            else:
                send("📭 اليوم لا يوجد - 10 فلاتر صارمة (هذا جيد)")
            playbook_date = today_str

        # === 3. دخول/خروج 10/10 ===
        if playbook and (hour>16 or (hour==16 and now.minute>=35) or hour<3 or hour>=17):
            # ايقاف اذا خسرت مرتين
            if daily_losses >= MAX_LOSSES_PER_DAY:
                if f"stop_day_{today_str}" not in sent:
                    send(f"🛑 وقف تداول اليوم - خسارتين ({daily_losses})")
                    sent.add(f"stop_day_{today_str}")
                time.sleep(300)
                continue

            for sym in list(playbook.keys()):
                ind = get_indicators(sym)
                if not ind: continue
                price = ind['price']

                if sym not in entries:
                    # 10/10 دخول: EMA ترتيب + VWAP + فوليوم + RSI
                    trend_up = ind['ema9'] > ind['ema20'] and ind['ema20'] > ind['vwap']*0.995
                    vol_break = ind['last_vol'] > ind['avg_vol']*2.2
                    cond_break = price > ind['hod']*1.003 and vol_break and ind['rsi'] < 78 and trend_up
                    near_vwap = abs(price-ind['vwap'])/ind['vwap']*100 < 1.2
                    cond_vwap = near_vwap and price > ind['vwap'] and 48 < ind['rsi'] < 68 and ind['ema9'] > ind['ema20'] and vol_break

                    if cond_break and f"b_{sym}" not in sent:
                        risk = (PORTFOLIO*MAX_RISK_PER_TRADE/100)/(price*0.05)
                        entries[sym]=price
                        send(f"🚀 *{sym} كسر 10/10* ${price:.2f}\nHOD ${ind['hod']:.2f} | EMA9 {ind['ema9']:.2f}>20 {ind['ema20']:.2f}\nRSI {ind['rsi']:.0f} Vol {ind['last_vol']/ind['avg_vol']:.1f}x\nوقف ${price*0.95:.2f} | حجم {int(risk)} سهم (1%)\n[📈](https://www.tradingview.com/chart/?symbol={sym})")
                        sent.add(f"b_{sym}")
                        log_trade(sym, price, 0, 0, "دخول كسر")

                    elif cond_vwap and f"v_{sym}" not in sent:
                        entries[sym]=price
                        send(f"🟢 *{sym} VWAP+EMA 10/10* ${price:.2f}\nVWAP ${ind['vwap']:.2f} EMA9>20 Vol {ind['last_vol']/ind['avg_vol']:.1f}x")
                        sent.add(f"v_{sym}")

                else:
                    entry = entries[sym]
                    profit = (price-entry)/entry*100

                    if profit >= 25 and f"h_{sym}" not in sent:
                        send(f"💰 *نصف {sym} +{profit:.1f}%* ${entry:.2f}→${price:.2f}\nحرك الوقف للدخول")
                        sent.add(f"h_{sym}")
                        log_trade(sym, entry, price, profit, "نصف")

                    if profit >= 50 and f"f_{sym}" not in sent:
                        send(f"🔥 *75% {sym} +{profit:.1f}%* خل ربع مجاني")
                        sent.add(f"f_{sym}")

                    if profit <= -5:
                        if f"s_{sym}" not in sent:
                            send(f"⛔ *وقف {sym} {profit:.1f}%* ${price:.2f} | RSI {ind['rsi']:.0f}")
                            sent.add(f"s_{sym}")
                            log_trade(sym, entry, price, profit, "وقف")
                            del entries[sym]
                            daily_losses += 1

                    # وقف VWAP اذا كسر 2% تحت
                    if price < ind['vwap']*0.98 and sym in entries and f"vw_{sym}" not in sent and (price-entry)/entry*100 < 10:
                        send(f"⚠️ *{sym} كسر VWAP* ${price:.2f} < ${ind['vwap']:.2f}")
                        sent.add(f"vw_{sym}")

        if hour==3 and 5 <= now.minute < 10:
            # تقرير يومي
            if trades_log or candidates:
                send(f"📊 *تقرير اليوم* خسائر: {daily_losses} | مرشحين: {len(candidates)} | صفقات: {len(entries)}")
            candidates.clear(); playbook.clear(); entries.clear(); sent.clear(); playbook_date=""; daily_losses=0
            send("🌙 تصفير ULTIMATE - نبدأ 11ص")

        time.sleep(300)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)
