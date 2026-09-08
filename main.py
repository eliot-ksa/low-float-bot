import os, time, requests, schedule, pytz, threading
from datetime import datetime, timedelta

POLYGON_KEY = os.getenv("POLYGON_KEY", "")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("CHAT_ID", "")
KSA = pytz.timezone('Asia/Riyadh')

DONCHIAN_LEN = 20
ATR_BUFFER = 0.10
STOP_ATR_MULT = 2.0

# ── ارسال مع ازرار ──
def send_telegram(msg, with_button=True):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}
        if with_button:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": "🚀 جيب 5 اسهم $2-$5 الحين", "callback_data": "get_5"}],
                    [{"text": "📊 فحص سريع", "callback_data": "quick"}]
                ]
            }
        requests.post(url, json=payload, timeout=20)
    except Exception as e:
        print(f"TG error {e}")

def get_2_to_5():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        tickers = requests.get(url, timeout=20).json().get('tickers', [])
        return [t['ticker'] for t in tickers if 2 <= (t.get('day',{}).get('c',0) or t.get('lastTrade',{}).get('p',0) or 0) <= 5][:100]
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
        vols = [x['v'] for x in data]
        ema = sum(closes[-200:]) / 200
        trs = [max(data[i]['h']-data[i]['l'], abs(data[i]['h']-data[i-1]['c']), abs(data[i]['l']-data[i-1]['c'])) for i in range(1,len(data))]
        atr = sum(trs[-14:])/14
        upper = max(highs[-21:-1])
        last_close = closes[-1]
        vol_sma = sum(vols[-31:-1])/30
        if not (last_close > upper + atr*ATR_BUFFER and last_close > ema and vols[-1] > vol_sma*1.1 and vols[-1] > 400_000):
            return None
        return {
            'sym': ticker, 'price': last_close, 'buy': upper+atr*ATR_BUFFER,
            'stop': last_close - STOP_ATR_MULT*atr, 'tp1': last_close + atr*2, 'tp2': last_close + atr*4,
            'vol': vols[-1], 'score': (last_close-upper)/atr
        }
    except:
        return None

def job(manual=False):
    now = datetime.now(KSA)
    print(f"SCAN $2-$5 manual={manual} {now}")
    gainers = get_2_to_5()
    picks = []
    for s in gainers[:70]:
        r = calc(s)
        if r: picks.append(r)
        time.sleep(0.2)
    picks = sorted(picks, key=lambda x: x['score'], reverse=True)[:5]

    if not picks:
        send_telegram(f"🔍 *فحص {now.strftime('%H:%M')} KSA - $2-$5*\nفحصت {len(gainers)} سهم\nلا يوجد اختراق Donchian اليوم 😴")
        return

    msg = f"{'🔥 طلب فوري' if manual else '🚀 فحص تلقائي'} *TOP 5 - $2 الى $5 - {now.strftime('%H:%M')} KSA*\n"
    msg += f"مؤشرك: Donchian20 + EMA200\n━━━━━━━━━━━━━━━\n\n"
    for i,p in enumerate(picks,1):
        msg += f"*{i}. {p['sym']}* ${p['price']:.2f}\n"
        msg += f" 📍 شراء فوق: ${p['buy']:.2f}\n"
        msg += f" 🛑 ستوب: ${p['stop']:.2f} | 🎯 {p['tp1']:.2f} / {p['tp2']:.2f}\n\n"
    send_telegram(msg)

# ── يستقبل ضغطات الازرار ──
def telegram_listener():
    offset = 0
    print("Listener started...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={offset}&timeout=30"
            res = requests.get(url, timeout=35).json()
            for upd in res.get('result', []):
                offset = upd['update_id'] + 1
                # ضغط زر
                if 'callback_query' in upd:
                    data = upd['callback_query']['data']
                    # جواب للزر عشان يختفي التحميل
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                                  json={"callback_query_id": upd['callback_query']['id'], "text": "جاري الفحص..."}, timeout=10)
                    if data == 'get_5':
                        send_telegram("⏳ جاري فحص $2-$5...", with_button=False)
                        job(manual=True)
                    elif data == 'quick':
                        job(manual=True)
                # كتابة /stocks
                if 'message' in upd and 'text' in upd['message']:
                    txt = upd['message']['text'].lower()
                    if '/stocks' in txt or 'جيب' in txt or 'اسهم' in txt:
                        job(manual=True)
        except Exception as e:
            print(f"Listener error {e}")
            time.sleep(5)

# ── التشغيل ──
print("V14 Bot with Button Starting...")
threading.Thread(target=telegram_listener, daemon=True).start()

send_telegram(f"✅ *V14 اشتغل - مع زر $2-$5*\n⏰ تلقائي: 11ص | 4:30ع | 10م KSA\n👇 اضغطي الزر يجيب لك 5 اسهم الحين")

schedule.every().day.at("08:00").do(job)
schedule.every().day.at("13:30").do(job)
schedule.every().day.at("19:00").do(job)

job()

while True:
    schedule.run_pending()
    time.sleep(30)
