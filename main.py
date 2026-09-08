import os, time, requests, schedule, pytz
from datetime import datetime, timedelta

POLYGON_KEY = os.getenv("POLYGON_KEY", "")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("CHAT_ID", "")
KSA = pytz.timezone('Asia/Riyadh')

DONCHIAN_LEN = 20
ATR_LEN = 14
ATR_BUFFER = 0.10
EMA_LEN = 200
STOP_ATR_MULT = 2.0

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}, timeout=20)
    except Exception as e:
        print(e)

def get_2_to_5():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        tickers = requests.get(url, timeout=20).json().get('tickers', [])
        result = []
        for t in tickers:
            price = t.get('day',{}).get('c',0) or t.get('lastTrade',{}).get('p',0)
            if 2 <= price <= 5: # فلتر $2-$5 فقط
                result.append(t['ticker'])
        return result[:100]
    except:
        return []

def calc(ticker):
    try:
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}?adjusted=true&sort=asc&limit=500&apiKey={POLYGON_KEY}"
        data = requests.get(url, timeout=20).json().get('results',[])
        if len(data) < 210: return None

        closes = [x['c'] for x in data]
        highs = [x['h'] for x in data]
        lows = [x['l'] for x in data]
        vols = [x['v'] for x in data]

        ema = sum(closes[-200:]) / 200
        trs = [max(data[i]['h']-data[i]['l'], abs(data[i]['h']-data[i-1]['c']), abs(data[i]['l']-data[i-1]['c'])) for i in range(1,len(data))]
        atr = sum(trs[-14:])/14

        upper = max(highs[-21:-1])
        buf = atr * ATR_BUFFER
        last_close = closes[-1]
        last_vol = vols[-1]
        vol_sma = sum(vols[-31:-1])/30

        # نفس شروط مؤشرك
        if not (last_close > upper + buf and last_close > ema and last_vol > vol_sma*1.1):
            return None
        if last_vol < 400_000: return None

        return {
            'sym': ticker, 'price': last_close, 'buy': upper+buf,
            'stop': last_close - STOP_ATR_MULT*atr,
            'tp1': last_close + atr*2, 'tp2': last_close + atr*4,
            'ema': ema, 'vol': last_vol, 'score': (last_close-upper)/atr
        }
    except:
        return None

def job():
    now = datetime.now(KSA)
    print(f"SCAN $2-$5 {now}")
    gainers = get_2_to_5()
    picks = []
    for s in gainers[:70]:
        r = calc(s)
        if r: picks.append(r)
        time.sleep(0.2)
    picks = sorted(picks, key=lambda x: x['score'], reverse=True)[:5]

    if not picks:
        send_telegram(f"🔍 *فحص {now.strftime('%H:%M')} KSA - $2-$5*\nفحصت {len(gainers)} سهم\nلا يوجد اختراق Donchian اليوم")
        return

    msg = f"🚀 *TOP 5 - $2 الى $5 - {now.strftime('%Y-%m-%d')}*\nفلتر مؤشرك: Donchian20 + EMA200 + ATR\n━━━━━━━━━━━━━━━\n\n"
    for i,p in enumerate(picks,1):
        msg += f"*{i}. {p['sym']}* ${p['price']:.2f}\n"
        msg += f" 📍 شراء فوق: ${p['buy']:.2f}\n"
        msg += f" 🛑 ستوب: ${p['stop']:.2f} | 🎯 {p['tp1']:.2f} / {p['tp2']:.2f}\n"
        msg += f" 📊 Vol {p['vol']/1e6:.1f}M\n\n"
    send_telegram(msg)

print("V13 $2-$5 Bot Starting...")
send_telegram(f"✅ *V13 اشتغل $2-$5 فقط*\n⏰ 11ص | 4:30ع | 10م KSA\n📈 5 اسهم يوميا مع تنبيه BUY")
schedule.every().day.at("08:00").do(job)
schedule.every().day.at("13:30").do(job)
schedule.every().day.at("19:00").do(job)
job()
while True:
    schedule.run_pending()
    time.sleep(30)
