import os, time, requests, pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")

sent_today = set() # عشان ما يكرر نفس السهم

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        print(f"Sent: {msg[:100]}")
    except Exception as e:
        print(f"Send Error: {e}")

def is_allowed():
    tz = pytz.timezone('Asia/Riyadh')
    h = datetime.now(tz).hour
    return not (3 <= h < 11) # شغال من 11ص لـ 3ص

def get_float_and_news(symbol):
    try:
        # جيب خبر من Finnhub
        url = f"https://finnhub.io/api/v1/company-news?symbol={symbol}&from=2026-08-11&to=2026-08-13&token={FINNHUB_KEY}"
        news = requests.get(url, timeout=10).json()
        has_news = "✅" if len(news) > 0 else "❌"
        news_headline = news[0]['headline'][:80] if len(news) > 0 else "لا يوجد خبر"
    except:
        has_news = "❓"
        news_headline = "خطأ في الاخبار"

    # Polygon Float (تقريبي)
    try:
        url = f"https://api.polygon.io/v3/reference/tickers/{symbol}?apiKey={POLYGON_KEY}"
        data = requests.get(url, timeout=10).json()
        float_shares = data.get('results', {}).get('share_class_shares_outstanding', 0)
        if float_shares == 0:
            float_text = "غير معروف"
        else:
            float_text = f"{float_shares/1000000:.1f}M"
            if float_shares < 10000000:
                float_text += " 🔥 LOW FLOAT"
    except:
        float_text = "غير معروف"

    return float_text, has_news, news_headline

def scan_premarket():
    try:
        # سكنر Gainers + Most Active
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        gainers = requests.get(url, timeout=15).json().get('tickers', [])[:15]

        hot = []
        for t in gainers:
            sym = t.get('ticker')
            if sym in sent_today: continue

            price = t.get('day', {}).get('c', 0)
            vol = t.get('day', {}).get('v', 0)
            change = t.get('todaysChangePerc', 0)

            # شروط البري ماركت الذهبية
            if 1.5 < price < 10 and vol > 200000 and change > 10:
                float_text, has_news, headline = get_float_and_news(sym)

                # اذا Float قليل او فيه خبر نرسله
                if "LOW FLOAT" in float_text or "✅" in has_news or vol > 500000:
                    msg = f"🚨 *سهم ساخن قبل الافتتاح* 🚨\n\n*{sym}* - ${price:.2f} ({change:.1f}%)\nVol: {vol/1000:.0f}K\nFloat: {float_text}\nخبر: {has_news} {headline}\n\n[شارت](https://finance.yahoo.com/quote/{sym})"
                    hot.append(msg)
                    sent_today.add(sym)
                    time.sleep(2) # عشان لا يعلق Finnhub
        return hot
    except Exception as e:
        print(f"Scan Error: {e}")
        return []

send("🔥 البوت الاحترافي اشتغل\nبري ماركت سكنر من 11ص بتوقيت الرياض\nFloat + اخبار + Volume ✅")
print("Bot Pro Started...")

while True:
    try:
        if not is_allowed():
            sent_today.clear() # نفضي القائمة كل يوم جديد
            print("⏸️ نايم")
            time.sleep(60)
            continue

        now = datetime.now(pytz.timezone('Asia/Riyadh'))
        print(f"🔍 [{now.strftime('%H:%M:%S')}] فحص بري ماركت...")

        stocks = scan_premarket()
        for s in stocks:
            send(s)

        if not stocks:
            print("No hot stocks")

        time.sleep(60) # كل دقيقة

    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(15)
