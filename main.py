import os, time, requests, pytz
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

sent_premarket = set()
sent_rocket = set()

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
        print(f"Sent: {msg[:80]}")
    except Exception as e:
        print(f"Send Error: {e}")

def is_allowed():
    tz = pytz.timezone('Asia/Riyadh')
    h = datetime.now(tz).hour
    return not (3 <= h < 11) # شغال 11ص لـ 3ص

def get_float(symbol):
    try:
        url = f"https://api.polygon.io/v3/reference/tickers/{symbol}?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10).json()
        shares = r.get('results', {}).get('share_class_shares_outstanding')
        if not shares: return 999999999, "غير معروف"
        float_m = shares / 1000000
        txt = f"{float_m:.1f}M"
        if float_m < 5: txt += " 🔥🔥"
        elif float_m < 10: txt += " 🔥"
        return shares, txt
    except:
        return 999999999, "غير معروف"

def get_vwap_check(symbol):
    try:
        # نجيب اخر 30 دقيقة
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{from_date}/{to_date}?adjusted=true&sort=desc&limit=50&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10).json()
        bars = r.get('results', [])
        if len(bars) < 10: return 0, "لا يوجد"

        # حساب VWAP
        pv = sum(b['c'] * b['v'] for b in bars)
        vv = sum(b['v'] for b in bars)
        vwap = pv / vv if vv else 0
        last = bars[0]['c']

        diff = ((last - vwap) / vwap * 100) if vwap else 0

        if -3 <= diff <= 3:
            status = f"✅ عند VWAP ({diff:+.1f}%) - دخول محتمل"
        elif diff > 8:
            status = f"⚠️ بعيد فوق VWAP ({diff:+.1f}%) - خطر قمة"
        elif diff < -5:
            status = f"📉 تحت VWAP ({diff:+.1f}%) - انتظر ارتداد"
        else:
            status = f"قريب من VWAP ({diff:+.1f}%)"

        return vwap, status
    except Exception as e:
        return 0, f"خطأ VWAP {e}"

def scan():
    alerts = []
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)
        is_premarket = 11 <= now.hour < 16 or (now.hour == 16 and now.minute < 30)

        # جيب Gainers
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        gainers = requests.get(url, timeout=15).json().get('tickers', [])[:25]

        for t in gainers:
            sym = t.get('ticker')
            if not sym or len(sym) > 5: continue

            price = t.get('day', {}).get('c', 0)
            vol = t.get('day', {}).get('v', 0)
            change = t.get('todaysChangePerc', 0)

            # الشرط الاساسي
            if not (1.5 < price < 8 and vol > 200000): continue

            float_shares, float_txt = get_float(sym)

            # --- حركة المحترفين ---
            # 1- بري ماركت: 10%+ مع Float < 10M
            if is_premarket and change >= 10 and float_shares < 10000000 and sym not in sent_premarket:
                vwap, vwap_status = get_vwap_check(sym)
                msg = f"🚨 *بري ماركت ساخن (مرشح 50%)* 🚨\n\n*{sym}* - ${price:.2f} ({change:.1f}%)\nVol: {vol/1000:.0f}K\nFloat: {float_txt}\n{vwap_status}\n\n*خطة المحترف:* انتظر يلمس VWAP ويرتد بفوليوم\n[Chart](https://finance.yahoo.com/quote/{sym})"
                alerts.append(msg)
                sent_premarket.add(sym)
                time.sleep(1)

            # 2- بعد الافتتاح: اذا صار 30%+ ننبه انه يقترب من 50%
            elif not is_premarket and change >= 30 and sym not in sent_rocket:
                vwap, vwap_status = get_vwap_check(sym)
                if float_shares < 10000000: # فقط Low Float
                    msg = f"🚀 *يقترب من 50%* 🚀\n\n*{sym}* - ${price:.2f} ({change:.1f}%)\nVol: {vol/1000000:.1f}M\nFloat: {float_txt}\n{vwap_status}\n\n*انتبه:* اذا فوق VWAP بكثير لا تلحق قمة\n[Chart](https://finance.yahoo.com/quote/{sym})"
                    alerts.append(msg)
                    sent_rocket.add(sym)
                    time.sleep(1)

    except Exception as e:
        print(f"Scan Error: {e}")
    return alerts

send("🔥 *بوت المحترفين V3 اشتغل*\n11ص-4م: يصيد 10%+ Float<10M\n4:30م-3ص: ينبه اذا وصل 30%+ (مرشح 50%)\nمع فحص VWAP ✅")
print("Pro V3 Started")

while True:
    try:
        if not is_allowed():
            # تصفير كل يوم جديد الساعة 3 الفجر
            if datetime.now(pytz.timezone('Asia/Riyadh')).hour == 3:
                sent_premarket.clear()
                sent_rocket.clear()
            print("⏸️ نايم")
            time.sleep(60)
            continue

        print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] فحص محترفين...")
        msgs = scan()
        for m in msgs:
            send(m)
        if not msgs:
            print("No pro candidates")
        time.sleep(60)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(15)
