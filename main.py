import os
import requests
import time
from datetime import datetime
import pytz

# ========= اعداداتك هنا =========
TELEGRAM_TOKEN = os.getenv("8934617408:AAGU2IK8v7jMVxabU7mwFzLClxlENFBrbVA")
CHAT_ID = os.getenv("7565323308")
POLYGON_KEY = os.getenv("POLYGON_KEY", "") # اختياري، اذا ما عندك بيستخدم Finnhub المجاني
FINNHUB_KEY = os.getenv("d9rh3opr01qkdnrf1augd9rh3opr01qkdnrf1av0")

MIN_PRICE = 0.10
MAX_PRICE = 10.0

def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
    except Exception as e:
        print(f"TG Error {e}")

def scan_dynamic():
    """فحص ديناميكي - بدون اسهم ثابتة"""
    try:
        # نستخدم Polygon للسكانر الديناميكي - يجيب كل السوق مرة وحدة
        if POLYGON_KEY:
            url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}&limit=100"
            data = requests.get(url, timeout=15).json()
            tickers_data = data.get("tickers", [])
        else:
            # Fallback مجاني من Finnhub
            url = f"https://finnhub.io/api/v1/scan/technical?token={FINNHUB_KEY}"
            # Finnhub ما عنده gainers مجاني، نستخدم قائمة اكثر الاسهم تداولا كبديل مؤقت
            # الحل الافضل تجيب مفتاح Polygon المجاني (يبدأ مجاني)
            return []

        alerts = []
        for t in tickers_data:
            day = t.get("day", {})
            prev = t.get("prevDay", {})
            price = day.get("c", 0)
            prev_close = prev.get("c", 0)
            if prev_close == 0: continue

            # شرط 1: سعرك
            if not (MIN_PRICE <= price <= MAX_PRICE):
                continue

            gap = ((price - prev_close) / prev_close) * 100
            volume = day.get("v", 0)
            
            # شرط 2 و 3: Gap + Volume
            if gap < 10 or volume < 200000:
                continue

            # شرط 4: مقاومة 5 ايام - نفس دوائرك $4.7 و $2.53
            ticker = t["ticker"]
            try:
                agg_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/2026-08-01/2026-08-11?apiKey={POLYGON_KEY}"
                agg = requests.get(agg_url, timeout=10).json()
                if agg.get("results"):
                    resistance = max([x["h"] for x in agg["results"][-5:]])
                    # اذا قريب من المقاومة او اخترقها
                    if price >= resistance * 0.96:
                        emoji = "🚀" if price > resistance else "👀"
                        alerts.append(f"{emoji} *{ticker}* ${price:.2f} | Gap %{gap:.1f} | Vol {volume:,}\n   مقاومة 5 ايام: ${resistance:.2f} -> {'اختراق' if price>resistance else 'عند المقاومة'}")
            except:
                continue

        return alerts
    except Exception as e:
        print(f"Scan error: {e}")
        return []

def main():
    send_tg(f"✅ *بوت الاختراقات اشتغل*\n💰 الفلتر: ${MIN_PRICE} - ${MAX_PRICE}\n⏰ كل 5 دقايق\n🔍 ديناميكي - بدون اسهم ثابتة\nالنمط: اختراق مقاومة مثل XHLD $4.7 / SCKT $0.75")
    
    while True:
        try:
            ny = datetime.now(pytz.timezone('America/New_York'))
            ksa = datetime.now(pytz.timezone('Asia/Riyadh'))
            is_market_time = (7 <= ny.hour <= 16) # 7 صباحا الى 4 مساء نيويورك = 2 الظهر الى 11 ليلا الرياض

            if is_market_time:
                alerts = scan_dynamic()
                if alerts:
                    header = f"📈 *تنبيهات {ksa.strftime('%I:%M %p')} بتوقيت الرياض*\nالسوق: {'مفتوح' if 9 <= ny.hour < 16 else 'بريماركت'}\n\n"
                    msg = header + "\n\n".join(alerts[:8])
                    send_tg(msg)
                else:
                    # لا يرسل اذا ما فيه شي عشان لا يزعجك - تقدر تفعلها
                    print(f"{ksa.strftime('%H:%M')} - فحص: لا يوجد سهم مطابق للشروط")

            else:
                print(f"خارج وقت السوق - نايم - {ksa}")

            time.sleep(300) # كل 5 دقايق بالضبط
        except Exception as e:
            print(f"Loop error {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
