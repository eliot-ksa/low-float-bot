import os, time, requests, schedule, pytz
from datetime import datetime, timedelta

# اساميك انتي اللي في الصورة
POLYGON_KEY = os.getenv("POLYGON_KEY", "")
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "")import os
import time
import requests
from datetime import datetime, timedelta
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
POLYGON_KEY = os.getenv("POLYGON_KEY")

KSA_TZ = pytz.timezone('Asia/Riyadh')
ET_TZ = pytz.timezone('America/New_York')

WATCHLIST_FILE = "/tmp/watchlist.txt"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": False}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(e)

def get_gappers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=15).json()
        tickers = r.get('tickers', [])[:50]
        results = []
        for t in tickers:
            ticker = t.get('ticker')
            prev = t.get('prevDay', {})
            snap_url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}?apiKey={POLYGON_KEY}"
            s = requests.get(snap_url, timeout=10).json().get('ticker', {})
            pre = s.get('preMarket', {})
            pre_price = pre.get('p') or s.get('day',{}).get('c') or t.get('day',{}).get('c')
            pre_vol = pre.get('v', 0) or s.get('day',{}).get('v',0)
            prev_close = prev.get('c')
            if not prev_close or not pre_price: continue
            gap = ((pre_price - prev_close)/prev_close)*100
            if not (2 <= pre_price <= 20): continue
            if gap < 4: continue
            if pre_vol < 150000: continue
            results.append({"ticker":ticker,"price":pre_price,"gap":gap,"pre_vol":pre_vol,"prev_close":prev_close})
        return results
    except Exception as e:
        print(f"gappers error {e}")
        return []

def get_float_news(ticker):
    float_m, catalyst = None, "No news"
    try:
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={ticker}&token={FINNHUB_KEY}"
        p = requests.get(url, timeout=10).json()
        float_m = p.get('shareOutstanding')
    except: pass
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={ticker}&limit=1&apiKey={POLYGON_KEY}"
        n = requests.get(url, timeout=10).json().get('results', [])
        if n: catalyst = n[0].get('title','')[:120]
    except: pass
    return float_m, catalyst

def phase1_scan():
    now_ksa = datetime.now(KSA_TZ)
    send_telegram(f"⏰ *فحص ما قبل الافتتاح* - {now_ksa.strftime('%H:%M')} KSA")
    gappers = get_gappers()
    final = []
    for g in gappers[:10]:
        fm, cat = get_float_news(g['ticker'])
        if fm and fm > 20: continue
        g['float_m']=fm; g['catalyst']=cat
        final.append(g)
        time.sleep(0.8)
    if not final:
        send_telegram("😴 لا يوجد سهم مطابق حالياً")
        return []
    final = sorted(final, key=lambda x: x['gap'], reverse=True)[:3]
    # حفظ القائمة للمرحلة الثانية
    with open(WATCHLIST_FILE,'w') as f:
        f.write(",".join([x['ticker'] for x in final]))
    
    msg = f"🔥 *Watchlist {now_ksa.strftime('%Y-%m-%d')}* 🔥\n\n"
    for i,s in enumerate(final,1):
        ft = f"{s['float_m']:.1f}M" if s['float_m'] else "N/A"
        msg+=f"*{i}. ${s['ticker']}* ${s['price']:.2f} Gap +{s['gap']:.1f}%\n VolPre: {s['pre_vol']:,} Float: {ft}\n 📰 {s['catalyst']}\n 📈 https://www.tradingview.com/symbols/{s['ticker']}/ \n\n"
    msg+="⏳ سأبدأ مراقبة كسر VWAP بعد افتتاح السوق 4:30 بتوقيت السعودية"
    send_telegram(msg)
    return final

def get_vwap_data(ticker):
    """يحسب VWAP من شموع الدقيقة اليوم"""
    try:
        today_et = datetime.now(ET_TZ).strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{today_et}/{today_et}?adjusted=true&sort=asc&limit=500&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10).json()
        bars = r.get('results', [])
        if len(bars) < 10: return None, None, None
        cum_pv = 0
        cum_v = 0
        vwap_list = []
        for b in bars:
            typical = (b['h']+b['l']+b['c'])/3
            pv = typical * b['v']
            cum_pv += pv
            cum_v += b['v']
            vwap = cum_pv / cum_v if cum_v else 0
            vwap_list.append(vwap)
        last_price = bars[-1]['c']
        last_vwap = vwap_list[-1]
        # هل اخر شمعتين فوق VWAP؟
        prev_price = bars[-2]['c']
        prev_vwap = vwap_list[-2]
        return last_price, last_vwap, (prev_price < prev_vwap and last_price > last_vwap)
    except Exception as e:
        print(f"vwap error {ticker} {e}")
        return None, None, False

def phase2_monitor():
    # يقرأ القائمة
    try:
        with open(WATCHLIST_FILE,'r') as f:
            tickers = f.read().split(",")
    except:
        send_telegram("⚠️ لا يوجد Watchlist محفوظة، سأفحص من جديد")
        tickers = [x['ticker'] for x in phase1_scan()]
    
    if not tickers or tickers == ['']: return
    send_telegram(f"👀 *بدأت مراقبة VWAP* للأسهم: {', '.join(['$'+t for t in tickers])}\nسأرسل تنبيه عند كسر VWAP صعوداً مع حجم")
    
    alerted = set()
    # راقب لمدة ساعتين بعد الافتتاح (4:30-6:30 KSA)
    end_time = datetime.now(KSA_TZ) + timedelta(hours=2)
    while datetime.now(KSA_TZ) < end_time:
        for ticker in tickers:
            if ticker in alerted: continue
            price, vwap, is_cross = get_vwap_data(ticker)
            if not price: continue
            # شرط الدخول: كسر VWAP + السعر فوق VWAP + حجم لحظي عالي
            if is_cross or (price > vwap * 1.005): # 0.5% فوق VWAP لتأكيد
                send_telegram(f"🚀 *تنبيه دخول* 🚀\n\n${ticker} كسر VWAP الآن!\nالسعر: ${price:.2f}\nVWAP: ${vwap:.2f}\n📈 ادخل مع كسر هاي الشمعة ووقفك تحت VWAP مباشرة\nhttps://www.tradingview.com/symbols/{ticker}/")
                alerted.add(ticker)
        if len(alerted) == len(tickers):
            break
        time.sleep(60) # فحص كل دقيقة
    
    send_telegram("✅ انتهت فترة مراقبة VWAP اليوم")

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv)>1 else "phase1"
    if mode == "phase1":
        phase1_scan()
    elif mode == "phase2":
        phase2_monitor()
    else:
        # auto detect by time KSA
        now = datetime.now(KSA_TZ)
        # قبل 4:30 = phase1 , بعد 4:30 = phase2
        if now.hour < 16 or (now.hour==16 and now.minute<30):
            phase1_scan()
        else:
            phase2_monitor()

TELEGRAM_CHAT = os.getenv("CHAT_ID", "")

KSA = pytz.timezone('Asia/Riyadh')

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(f"No telegram keys")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        print("Telegram sent ✅")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        return requests.get(url, timeout=15).json().get('tickers', [])
    except Exception as e:
        print(f"Gainers error: {e}")
        return []

def get_details(sym):
    try:
        snap = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=15).json()
        ticker = snap.get('ticker',{})
        day = ticker.get('day',{})
        prev = ticker.get('prevDay',{})
        price = day.get('c',0)
        if price == 0: return None
        change = ((price - prev.get('c',1)) / prev.get('c',1) * 100) if prev.get('c') else 0
        vol = day.get('v',0)
        
        hist = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/day/{(datetime.now()-timedelta(days=100)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?apiKey={POLYGON_KEY}", timeout=15).json()
        results = hist.get('results',[])
        if len(results) < 25: return None
        closes = [b['c'] for b in results]
        vols = [b['v'] for b in results]
        
        avg_vol = sum(vols[-20:-1]) / 19 if len(vols)>20 else 0
        rel_vol = vol / avg_vol if avg_vol else 0
        sma20 = sum(closes[-20:]) / 20
        sma50 = sum(closes[-50:]) / 50 if len(closes)>=50 else sma20*0.9
        high_90 = max(closes[-90:]) if len(closes)>=90 else max(closes)
        low_90 = min(closes[-90:]) if len(closes)>=90 else min(closes)
        box_range = (high_90 - low_90) / low_90 if low_90 else 1
        vwap = day.get('vw', price)
        
        return {
            'sym': sym, 'price': price, 'change': change, 'vol': vol,
            'rel_vol': rel_vol, 'avg_vol': avg_vol,
            'sma20': sma20, 'sma50': sma50,
            'high_90': high_90, 'low_90': low_90, 'box_range': box_range,
            'vwap': vwap
        }
    except:
        return None

def scan():
    gainers = get_gainers()
    picks = []
    for t in gainers[:50]:
        sym = t.get('ticker')
        if not sym: continue
        d = get_details(sym)
        if not d: continue
        if not (10 <= d['change'] <= 150): continue
        if d['price'] < d['sma20']: continue
        if not (d['sma50'] < d['sma20']): continue
        if d['avg_vol'] < 300_000: continue
        if d['rel_vol'] < 2.0: continue
        if d['vol'] < 1_000_000: continue
        if d['price'] < 1 or d['price'] > 25: continue
        if d['box_range'] > 0.50: continue
        score = d['rel_vol'] + (d['change']/20)
        if d['price'] > d['high_90']*0.98: score+=2
        d['score'] = score
        picks.append(d)
    return sorted(picks, key=lambda x: x['score'], reverse=True)[:3]

def job():
    try:
        now_ksa = datetime.now(KSA)
        hour = now_ksa.hour
        if 3 <= hour < 11:
            print(f"{now_ksa.strftime('%H:%M')} KSA - نايم")
            return
        print(f"{now_ksa.strftime('%H:%M')} KSA - يفحص السوق...")
        picks = scan()
        if not picks:
            print("No picks")
            return
        for p in picks:
            msg = f"""
🚀 *V11 PICK - {p['sym']}*
💰 ${p['price']:.2f} | 📈 +{p['change']:.1f}%
🔥 RelVol: {p['rel_vol']:.1f}x | 📦 {p['vol']/1_000_000:.1f}M
🎯 بوكس: {p['low_90']:.2f} - {p['high_90']:.2f}$
*دخول:* فوق ${p['vwap']:.2f}
*وقف:* ${p['low_90']:.2f}
*وقت:* {now_ksa.strftime('%H:%M')} KSA
"""
            send_telegram(msg)
            time.sleep(1)
    except Exception as e:
        print(f"Job error: {e}")

print("V11 Bot Starting...")
send_telegram(f"✅ *V11 اشتغل*\n⏰ من 11 الصبح الى 3 الفجر KSA\n📅 {datetime.now(KSA).strftime('%H:%M')} KSA")

schedule.every(5).minutes.do(job)
job()

while True:
    try:
        schedule.run_pending()
        time.sleep(30)
    except Exception as e:
        print(f"Loop error: {e}")
        time.sleep(60)
