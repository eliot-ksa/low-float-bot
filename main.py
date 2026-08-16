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
    except Exception as e:
        print(e)

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
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{yesterday}/{today}?adjusted=true&sort=desc&limit=100&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=15).json().get('results', [])
        if len(bars) < 20: return None

        bars = list(reversed(bars)) # نخليها من القديم للجديد عشان RSI
        last_50 = bars[-50:]

        pv = sum(b['c']*b['v'] for b in last_50)
        vv = sum(b['v'] for b in last_50)
        vwap = pv/vv if vv else last_50[-1]['c']

        hod = max(b['h'] for b in last_50)
        lod = min(b['l'] for b in last_50)

        # RSI صحيح
        closes = [b['c'] for b in bars[-15:]]
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(max(0, diff))
            losses.append(max(0, -diff))
        avg_gain = sum(gains)/14 if gains else 0
        avg_loss = sum(losses)/14 if losses else 0.001
        rs = avg_gain/(avg_loss or 0.001)
        rsi = 100 - (100/(1+rs))

        last = bars[-1]
        avg_vol = sum(b['v'] for b in bars[-21:-1])/20 if len(bars)>21 else last['v']

        return {
            'price': last['c'],
            'vwap': vwap,
            'hod': hod,
            'lod': lod,
            'rsi': rsi,
            'last_vol': last['v'],
            'avg_vol': avg_vol or 1,
        }
    except Exception as e:
        print(f"ind {sym} {e}")
        return None

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        return requests.get(url, timeout=15).json().get('tickers', [])
    except: return []

send("✅ *V9.1 مصحح اشتغل - 11ص الى 3 الفجر*")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)
        hour = now.hour
        today_str = str(now.date())

        active_time = (11 <= hour <= 23) or (0 <= hour < 3)
        if not active_time:
            time.sleep(60)
            continue

        # 1. تجميع
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
                candidates.append({'sym': sym, 'price': price, 'change': change, 'float': f})
                send(f"🔍 مرشح: *{sym}* ${price:.2f} +{change:.1f}%")
                time.sleep(1)

        # 2. PlayBook 4:30
        if hour==16 and 30 <= now.minute < 35 and playbook_date!= today_str:
            # تصفير sent حق امس
            sent.clear()
            entries.clear()
            if candidates:
                top = sorted(candidates, key=lambda x: x['change'], reverse=True)[:3]
                playbook = {c['sym']: c for c in top}
                msg = f"📘 *PlayBook {now.strftime('%m/%d')}*\n\n"
                for i,c in enumerate(top,1):
                    msg+=f"{i}. *{c['sym']}* ${c['price']:.2f} +{c['change']:.1f}%\n"
                msg+="\n⏰ مراقبة كل 5 دقايق الى 3 الفجر"
                send(msg)
            else:
                send("📭 اليوم لا يوجد")
            playbook_date = today_str

        # 3. مراقبة
        if playbook and (hour>16 or (hour==16 and now.minute>=35) or hour<3 or hour>=17):
            for sym in list(playbook.keys()):
                ind = get_indicators(sym)
                if not ind: continue
                price = ind['price']

                if sym not in entries:
                    cond_break = price > ind['hod']*1.003 and ind['last_vol'] > ind['avg_vol']*1.8 and ind['rsi'] < 75
                    near_vwap = abs(price - ind['vwap'])/ind['vwap']*100 < 1.5
                    cond_vwap = near_vwap and price > ind['vwap'] and 45 < ind['rsi'] < 68

                    if cond_break and f"break_{sym}" not in sent:
                        entries[sym] = price
                        send(f"🚀 *كسر قمة {sym}* ${price:.2f}\nقمة ${ind['hod']:.2f} | RSI {ind['rsi']:.0f}\nوقف: ${price*0.95:.2f} (-5%)")
                        sent.add(f"break_{sym}")
                    elif cond_vwap and f"vwap_{sym}" not in sent:
                        entries[sym] = price
                        send(f"🟢 *VWAP {sym}* ${price:.2f} | VWAP ${ind['vwap']:.2f}\nRSI {ind['rsi']:.0f}")
                        sent.add(f"vwap_{sym}")
                else:
                    entry = entries[sym]
                    profit = (price-entry)/entry*100
                    if profit >= 25 and f"half_{sym}" not in sent:
                        send(f"💰 *نصف {sym} +{profit:.1f}%* دخول ${entry:.2f} -> ${price:.2f}")
                        sent.add(f"half_{sym}")
                    if profit >= 50 and f"full_{sym}" not in sent:
                        send(f"🔥 *75% {sym} +{profit:.1f}%*")
                        sent.add(f"full_{sym}")
                    if profit <= -5:
                        if f"stop_{sym}" not in sent:
                            send(f"⛔ *وقف {sym} {profit:.1f}%*")
                            sent.add(f"stop_{sym}")
                            del entries[sym]
                    if ind['rsi'] > 83 and f"rsi_{sym}" not in sent:
                        send(f"⚠️ *{sym} RSI {ind['rsi']:.0f} متشبع*")
                        sent.add(f"rsi_{sym}")

        if hour==3 and 5 <= now.minute < 10:
            candidates.clear()
            playbook.clear()
            entries.clear()
            sent.clear()
            playbook_date = ""
            send("🌙 تصفير - نبدأ 11ص")

        time.sleep(300)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)
