import os, time, requests, schedule, pytz
from datetime import datetime, timedelta

POLYGON_KEY = os.getenv("POLYGON_KEY", "")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("CHAT_ID", "")

KSA = pytz.timezone('Asia/Riyadh')

# ── اعدادات مؤشرك ──
DONCHIAN_LEN = 20
ATR_LEN = 14
ATR_BUFFER = 0.10
EMA_LEN = 200
STOP_ATR_MULT = 2.0
VOL_SMA_LEN = 30

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}, timeout=20)
    except Exception as e:
        print(f"TG error {e}")

def get_gainers_1_to_15():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        tickers = requests.get(url, timeout=15).json().get('tickers', [])
        # فلتر 1-15 دولار
        filtered = []
        for t in tickers:
            ticker_data = t.get('ticker',{})
            day = t.get('day',{}) if 'day' in t else ticker_data.get('day',{})
            # السعر من snapshot
            price = t.get('day',{}).get('c',0) or t.get('lastTrade',{}).get('p',0)
            if 1 <= price <= 15:
                filtered.append(t.get('ticker'))
        return filtered[:100]
    except Exception as e:
        print(e)
        return []

def calc_indicator(sym):
    try:
        # جيب 250 يوم عشان EMA200
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/day/{from_date}/{to_date}?adjusted=true&apiKey={POLYGON_KEY}"
        data = requests.get(url, timeout=15).json().get('results',[])
        if len(data) < 210: return None

        closes = [x['c'] for x in data]
        highs = [x['h'] for x in data]
        lows = [x['l'] for x in data]
        vols = [x['v'] for x in data]

        # EMA 200
        ema = sum(closes[-200:]) / 200

        # ATR 14
        trs = []
        for i in range(1, len(data)):
            tr = max(data[i]['h']-data[i]['l'], abs(data[i]['h']-data[i-1]['c']), abs(data[i]['l']-data[i-1]['c']))
            trs.append(tr)
        atr = sum(trs[-14:]) / 14 if len(trs)>=14 else 0

        # Donchian 20 (بدون الشمعة الحالية - مثل كودك [1])
        upper = max(highs[-21:-1]) # اعلى 20 شمعة سابقة
        lower = min(lows[-21:-1])
        buf = atr * ATR_BUFFER

        last_close = closes[-1]
        last_vol = vols[-1]
        vol_sma = sum(vols[-31:-1]) / 30 if len(vols)>31 else last_vol
        vol_ok = last_vol > vol_sma * 1.2

        # شروطك
        buy_break = last_close > (upper + buf)
        trend_ok = last_close > ema

        if not (buy_break and trend_ok):
            return None

        # ستوب وهدف مثل كودك
        stop_price = last_close - STOP_ATR_MULT * atr
        target1 = last_close + atr * 2
        target2 = last_close + atr * 4

        # فلتر اضافي للبوت
        if last_vol < 500_000: return None

        score = (last_close - upper) / atr + (last_vol / vol_sma)

        return {
            'sym': sym, 'price': last_close, 'upper': upper, 'lower': lower,
            'buf': buf, 'buy_zone': upper + buf, 'stop': stop_price,
            'tp1': target1, 'tp2': target2, 'ema': ema, 'atr': atr,
            'vol': last_vol, 'vol_sma': vol_sma, 'score': score
        }
    except Exception as e:
        print(f"{sym} error {e}")
        return None

def daily_job():
    try:
        now = datetime.now(KSA)
        if 3 <= now.hour < 11:
            return
        print(f"{now} - فحص 1$-15$ Breakout...")
        gainers = get_gainers_1_to_15()
        picks = []
        for sym in gainers[:60]:
            d = calc_indicator(sym)
            if d: picks.append(d)
            time.sleep(0.2)

        picks = sorted(picks, key=lambda x: x['score'], reverse=True)[:5]

        if not picks:
            send_telegram(f"🔍 *فحص {now.strftime('%H:%M')} KSA*\nلا يوجد اختراقات Donchian اليوم ضمن $1-$15")
            return

        msg = f"🚀 *TOP 5 اختراقات اليوم - {now.strftime('%Y-%m-%d')}*\n*فلتر: $1-$15 + Donchian 20 + EMA200*\n\n"
        for i,p in enumerate(picks,1):
            msg += f"*{i}. {p['sym']}* - ${p['price']:.2f}\n"
            msg += f" 📍 شراء فوق: ${p['buy_zone']:.2f} (Donchian {p['upper']:.2f}+ATR)\n"
            msg += f" 🛑 ستوب: ${p['stop']:.2f}\n"
            msg += f" 🎯 هدف1: ${p['tp1']:.2f} | هدف2: ${p['tp2']:.2f}\n"
            msg += f" 📊 EMA200: ${p['ema']:.2f} | Vol: {p['vol']/1e6:.1f}M\n\n"

        send_telegram(msg)

    except Exception as e:
        print(f"daily error {e}")
        send_telegram(f"❌ خطأ: {e}")

# بداية
print("V12 Breakout Bot Starting...")
send_telegram(f"✅ *V12 اشتغل - نسخة مؤشرك*\n⏰ يرسل 5 اسهم يوميا $1-$15\n📈 Donchian {DONCHIAN_LEN} + EMA {EMA_LEN} + ATR {ATR_LEN}\n⏰ {datetime.now(KSA).strftime('%H:%M')} KSA")

schedule.every(10).minutes.do(daily_job)

# شغلي اول فحص الحين
daily_job()

while True:
    schedule.run_pending()
    time.sleep(30)
