import os
import requests
import time
from datetime import datetime
import pytz

# ========== الاعدادات من Railway Variables ==========
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")

MIN_PRICE = 0.10
MAX_PRICE = 10.0

def send_tg(msg):
    try:
        if not TELEGRAM_TOKEN or not CHAT_ID:
            print("Missing BOT_TOKEN or CHAT_ID")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": CHAT_ID, 
            "text": msg, 
            "parse_mode": "Markdown", 
            "disable_web_page_preview": True
        }, timeout=15)
        print(f"Sent: {msg[:50]}")
    except Exception as e:
        print(f"TG Error {e}")

def scan_dynamic():
    alerts = []
    try:
        tickers_data = []
        
        # اذا عندك Polygon (الافضل)
        if POLYGON_KEY:
            url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}&limit=100"
            data = requests.get(url, timeout=15).json()
            tickers_data = data.get("tickers", [])
            
            for t in tickers_data:
                day = t.get("day", {})
                prev = t.get("prevDay", {})
                price = day.get("c", 0)
                prev_close = prev.get("c", 0)
                if prev_close == 0:
                    continue
                if not (MIN_PRICE <= price <= MAX_PRICE):
                    continue
                
                change_percent = ((price - prev_close) / prev_close) * 100
                if change_percent >= 10:  # صاعد 10%+
                    symbol = t.get("ticker", "")
                    alerts.append(f"🚀 *{symbol}* ${price:.2f} (+{change_percent:.1f}%) | Vol: {day.get('v',0):,}")
        
        else:
            # استخدام Finnhub المجاني - نفحص قائمة اسهم اللو فلوت المشهورة
            # Finnhub ما يعطي gainers مجاني، فنستخدم طريقة ثانية
            # نفحص اكثر الاسهم تداولاً اليوم
            print("Using Finnhub fallback...")
            # تقدر تضيف هنا لستة اسهمك المفضلة للفحص
            test_symbols = ["FFIE", "GME", "AMC", "BBBY", "MULN", "NVAX"]
            for symbol in test_symbols:
                try:
                    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_KEY}"
                    r = requests.get(url, timeout=10).json()
                    price = r.get("c", 0)
                    prev_close = r.get("pc", 0)
                    if prev_close == 0 or price == 0:
                        continue
                    if not (MIN_PRICE <= price <= MAX_PRICE):
                        continue
                    change = ((price - prev_close) / prev_close) * 100
                    if change >= 5:
                        alerts.append(f"🚀 *{symbol}* ${price:.2f} (+{change:.1f}%)")
                except:
                    continue
                time.sleep(0.5)  # عشان لا نتجاوز الحد المجاني

    except Exception as e:
        print(f"Scan Error {e}")
    
    return alerts

# ========== التشغيل الرئيسي ==========
if __name__ == "__main__":
    print("Bot Started...")
    send_tg("🚀 البوت اشتغل بنجاح على Railway ✅\nالفحص الديناميكي بدأ...")

    while True:
        try:
            # مواقيت السوق الامريكي 9:30 ص - 4:00 م بتوقيت نيويورك
            ny_tz = pytz.timezone('America/New_York')
            now_ny = datetime.now(ny_tz)
            
            # فحص فقط وقت السوق (الاثنين للجمعة)
            if now_ny.weekday() < 5:  # 0-4 = Mon-Fri
                alerts = scan_dynamic()
                for alert in alerts:
                    send_tg(alert)
                    time.sleep(2)
            else:
                print(f"Weekend - {now_ny}")

            # انتظر 5 دقايق بين كل فحص
            time.sleep(300)

        except Exception as e:
            print(f"Main Loop Error {e}")
            time.sleep(60)
