import os, time, requests, schedule, pytz
from datetime import datetime, timedelta

# نفس المفاتيح اللي عندك في الصورة
POLYGON_KEY = os.getenv("POLYGON_KEY", "")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "")
TELEGRAM_CHAT = os.getenv("CHAT_ID", "")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")

KSA = pytz.timezone('Asia/Riyadh')
ET = pytz.timezone('America/New_York')
WATCHLIST_FILE = "/tmp/watchlist.txt"

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(f"No telegram keys")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=15)
        print("Telegram sent ✅")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_gainers():
    """يجيب أسهم الفجوة قبل الافتتاح"""
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=15).json()
        tickers = r.get('tickers', [])[:50]
        results = []
        for t in tickers:
            ticker = t.get('ticker')
            prev = t.get('prevDay', {})
            # تفاصيل أكثر لكل سهم
            snap_url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}?apiKey={POLYGON_KEY}"
            s = requests.get(snap_url, timeout=10).json().get('ticker', {})
            pre = s.get('preMarket', {})
            pre_price = pre.get('p') or s.get('day',{}).get('c') or t.get('day',{}).get('c')
            pre_vol = pre.get('v', 0) or s.get('day',{}).get('v', 0)
            prev_close = prev.get('c')
            if not prev_close or not pre_price:
                continue
            gap = ((pre_price - prev_close) / prev_close) * 100
            price = pre_price

            # الفلتر الأساسي اللي اتفقنا عليه
            if not (1.5 <= price <= 25): continue
            if gap < 4: continue
            if pre_vol < 150000: continue

            results.append({
                "ticker": ticker,
                "price": round(price,2),
                "gap": round(gap,2),
                "pre_vol": int(pre_vol),
                "prev_close": prev_close
            })
        return sorted(results, key=lambda x: x['gap'], reverse=True)
    except Exception as e:
        print(f"get_gainers error: {e}")
        return []

def get_float_and_news(ticker):
    float_m = None
    catalyst = "No recent catalyst"
    # Float من Finnhub
    if FINNHUB_KEY:
        try:
            url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_KEY}"
            p = requests.get(url, timeout=10).json()
            float_m = p.get('shareOutstanding')
        except: pass
    # خبر من Polygon
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={ticker}&limit=1&apiKey={POLYGON_KEY}"
        data = requests.get(url, timeout=10).json().get('results', [])
        if data:
            catalyst = data[0].get('title','')[:130]
    except: pass
    return float_m, catalyst

def phase1_scan():
    now = datetime.now(KSA)
    send_telegram(f"⏰ *فحص ما قبل الافتتاح* - {now.strftime('%H:%M')} KSA\nأبحث عن Gap>4% + Vol>150k + Price $1.5-$25...")
    gappers = get_gainers()
    final = []
    for g in gappers[:12]:
        fm, cat = get_float_and_news(g['ticker'])
        # فلتر Float < 20M - أهم فلتر للانفجارات
        if fm and fm > 20:
            continue
        g['float_m'] = fm
        g['catalyst'] = cat
        final.append(g)
        time.sleep(0.7)

    if not final:
        send_telegram("😴 لا يوجد سهم مطابق للفلتر حالياً")
        return []

    final = final[:3]
    # حفظ القائمة للمرحلة الثانية
    with open(WATCHLIST_FILE, 'w') as f:
        f.write(",".join([x['ticker'] for x in final]))

    msg = f"🔥 *Watchlist {now.strftime('%Y-%m-%d')}* 🔥\n\n"
    for i,s in enumerate(final,1):
        ft = f"{s['float_m']:.1f}M" if s['float_m'] else "N/A"
        emoji = "🚀" if s['gap'] > 8 else "⚡️"
        msg += f"{emoji} *{i}. ${s['ticker']}* ${s['price']} Gap +{s['gap']}%\n"
        msg += f" VolPre: {s['pre_vol']:,} | Float: {ft}\n"
        msg += f" 📰 {s['catalyst']}\n"
        msg += f" 📈 https://www.tradingview.com/symbols/{s['ticker']}/\n\n"
    msg += "⏳ سأراقب كسر VWAP بعد الافتتاح 4:30 KSA"
    send_telegram(msg)
    return final

def get_vwap_cross(ticker):
    """يحسب VWAP من شموع الدقيقة ويكشف كسره"""
    try:
        today = datetime.now(ET).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{today}/{today}?adjusted=true&sort=asc&limit=500&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10).json()
        bars = r.get('results', [])
        if len(bars) < 15: return None, None, False
        cum_pv, cum_v = 0, 0
        vwap_list = []
        for b in bars:
            typical = (b['h']+b['l']+b['c'])/3
            cum_pv += typical * b['v']
            cum_v += b['v']
            vwap_list.append(cum_pv/cum_v)
        last_price = bars[-1]['c']
        last_vwap = vwap_list[-1]
        prev_price = bars[-2]['c']
        prev_vwap = vwap_list[-2]
        is_cross = prev_price < prev_vwap and last_price > last_vwap
        return last_price, last_vwap, is_cross
    except:
        return None, None, False

def phase2_monitor():
    try:
        with open(WATCHLIST_FILE, 'r') as f:
            tickers = [x for x in f.read().split(",") if x]
    except:
        tickers = [x['ticker'] for x in phase1_scan()]
    if not tickers: return

    send_telegram(f"👀 *بدأت مراقبة VWAP* : {', '.join(['$'+t for t in tickers])}\nتنبيه عند كسر VWAP +0.5%")
    alerted = set()
    end = datetime.now(KSA) + timedelta(hours=2)
    while datetime.now(KSA) < end:
        for t in tickers:
            if t in alerted: continue
            price, vwap, cross = get_vwap_cross(t)
            if not price: continue
            if cross or price > vwap*1.005:
                send_telegram(f"🚀 *تنبيه دخول* 🚀\n\n${t} كسر VWAP!\nالسعر: ${price:.2f}\nVWAP: ${vwap:.2f}\nادخل بكسر هاي الشمعة ووقف تحت VWAP\nhttps://www.tradingview.com/symbols/{t}/")
                alerted.add(t)
        if len(alerted) == len(tickers): break
        time.sleep(60)
    send_telegram("✅ انتهت مراقبة اليوم")

# التشغيل التلقائي
if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if mode == "phase1": phase1_scan()
    elif mode == "phase2": phase2_monitor()
    else:
        now = datetime.now(KSA)
        if now.hour < 16 or (now.hour==16 and now.minute<30):
            phase1_scan()
        else:
            phase2_monitor()
