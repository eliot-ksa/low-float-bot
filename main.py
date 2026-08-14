import os, time, requests, pytz
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

daily_candidates = []
daily_top3 = {}
playbook_sent_date = ""
sent_events = set()

def send(m):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def get_gainers():
    try:
        url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=15).json()
        tickers = r.get('tickers', [])
        if tickers:
            print(f"Polygon رجع {len(tickers)}")
            return tickers
    except Exception as e:
        print(f"Polygon fail {e}")

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=100&offset=0&marketcap=micro"
        r = requests.get(url, headers=headers, timeout=15).json()
        rows = r.get('data',{}).get('rows',[])
        converted = []
        for row in rows[:60]:
            try:
                price = float(row['lastsale'].replace('$',''))
                change = float(row['pctchange'].replace('%',''))
                if 0.10 <= price <= 20 and change > 5:
                    converted.append({
                        'ticker': row['symbol'],
                        'day': {'c': price, 'v': 500000},
                        'todaysChangePerc': change
                    })
            except: continue
        if converted:
            print(f"Nasdaq رجع {len(converted)}")
            return converted
    except Exception as e:
        print(f"Nasdaq fail {e}")

    return []

def get_vwap_data(sym):
    try:
        from datetime import timedelta
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?adjusted=true&sort=desc&limit=30&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results', [])
        if len(bars) < 5: return None
        pv = sum(b['c']*b['v'] for b in bars)
        vv = sum(b['v'] for b in bars)
        vwap = pv/vv if vv else bars[0]['c']
        return {'vwap': vwap, 'last': bars[0]['c'], 'prev': bars[1]['c'], 'last_vol': bars[0]['v'], 'prev_vol': bars[1]['v'] or 1}
    except: return None

def get_score(sym, price, change, vol):
    score = change * 2 + min(vol/100000, 20)
    if change > 15: score += 20
    if 0.10 <= price < 1: score += 15
    elif 1 <= price < 5: score += 10
    return score, 0, "?"

def check_entry_signal(sym):
    vd = get_vwap_data(sym)
    if not vd: return False, ""
    diff_pct = ((vd['last'] - vd['vwap'])/vd['vwap']*100)
    is_near = -1.5 <= diff_pct <= 1.5
    is_bullish = vd['last'] > vd['prev']
    is_vol = vd['last_vol'] > vd['prev_vol'] * 1.4
    if is_near and is_bullish and is_vol:
        return True, f"VWAP ${vd['vwap']:.2f} | السعر ${vd['last']:.2f} ({diff_pct:+.1f}%) Vol {vd['last_vol']/vd['prev_vol']:.1f}x"
    return False, ""

def build_playbook():
    global daily_top3
    if not daily_candidates:
        send(f"📭 اليوم فحصنا {len(daily_candidates)} بس السوق هادي - بكرة 11ص بنحاول")
        return
    sorted_cands = sorted(daily_candidates, key=lambda x: x['score'], reverse=True)[:3]
    daily_top3 = {c['sym']: {'entered': False, 'entry_price': 0} for c in sorted_cands}
    msg = f"📘 *PLAYBOOK {datetime.now().strftime('%m/%d')} - من 0.10$ الى 20$*\nفحصنا {len(daily_candidates)} سهم - افضل 3:\n\n"
    for i,c in enumerate(sorted_cands,1):
        msg+=f"{i}. *{c['sym']}* ${c['price']:.2f} (+{c['change']:.1f}%)\n"
    msg+="\n⏳ انتظر اشارة 🟢 دخول"
    send(msg)

send("✅ *V7.1 اشتغل - سعر 0.10 الى 20$*\n11ص الى 4م مراقبة\n11:20 PlayBook\nبعدها اشارات دخول وخروج")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)

        if 11 <= now.hour <= 23:
            gainers = get_gainers()
            print(f"{now.strftime('%H:%M:%S')} - لقى {len(gainers)}")

            for t in gainers[:50]:
                sym = t.get('ticker')
                if not sym or any(c['sym']==sym for c in daily_candidates): continue
                price = t.get('day',{}).get('c',0)
                change = t.get('todaysChangePerc',0)
                vol = t.get('day',{}).get('v',0) or 300000

                # السعر من 0.10 الى 20
                if not (0.10 <= price <= 20 and change > 5):
                    continue

                score, _, _ = get_score(sym, price, change, vol)
                daily_candidates.append({'sym': sym, 'price': price, 'change': change, 'vol': vol, 'score': score})
                send(f"🔍 مرشح: *{sym}* +{change:.1f}% ${price:.2f}")
                time.sleep(0.5)

        if now.hour == 11 and now.minute == 20 and playbook_sent_date!= str(now.date()):
            build_playbook()
            playbook_sent_date = str(now.date())

        # مراقبة دخول
        if daily_top3 and now.hour >= 11:
            try:
                gainers = get_gainers()
                gmap = {t.get('ticker'): t for t in gainers}
                for sym in list(daily_top3.keys()):
                    if sym not in gmap: continue
                    t = gmap[sym]
                    price = t.get('day',{}).get('c',0)
                    change = t.get('todaysChangePerc',0)

                    if not daily_top3[sym]['entered']:
                        is_entry, detail = check_entry_signal(sym)
                        key = f"entry_{sym}_{now.strftime('%H%M')}"
                        if is_entry and key not in sent_events:
                            daily_top3[sym]['entered'] = True
                            daily_top3[sym]['entry_price'] = price
                            send(f"🟢 *دخول {sym} الان*\n{detail}\nالسعر ${price:.2f} (+{change:.1f}%)\nوقف 7%\n[📈 الشارت](https://www.tradingview.com/chart/?symbol={sym})")
                            sent_events.add(key)
                    else:
                        entry = daily_top3[sym]['entry_price']
                        profit = ((price - entry)/entry*100) if entry else 0
                        if profit >= 35 and f"sell_half_{sym}" not in sent_events:
                            send(f"💰 *بيع نصف {sym}* دخول ${entry:.2f} | الان ${price:.2f} (+{profit:.1f}%)")
                            sent_events.add(f"sell_half_{sym}")
                        if change >= 45 and f"rocket_{sym}" not in sent_events:
                            send(f"🚀 *{sym} وصل 45%+* الان +{change:.1f}%")
                            sent_events.add(f"rocket_{sym}")
                        if profit <= -7 and f"stop_{sym}" not in sent_events:
                            send(f"⛔ *وقف {sym}* {profit:.1f}%")
                            sent_events.add(f"stop_{sym}")
            except: pass

        time.sleep(45)
    except Exception as e:
        print(e)
        time.sleep(15)
