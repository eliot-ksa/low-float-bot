import os, time, requests, pytz
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
POLYGON_KEY = os.getenv("POLYGON_KEY")

daily_candidates = []
daily_top3 = {} # sym -> {price, float_txt, entered, entry_price}
playbook_sent_date = ""
sent_events = set()

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": False}, timeout=15)
    except: pass

def is_allowed():
    h = datetime.now(pytz.timezone('Asia/Riyadh')).hour
    return not (3 <= h < 11)

def get_float(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=10).json()
        return r.get('results', {}).get('share_class_shares_outstanding', 0)
    except: return 0

def get_vwap_data(sym):
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{sym}/range/1/minute/{(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')}/{datetime.now().strftime('%Y-%m-%d')}?adjusted=true&sort=desc&limit=30&apiKey={POLYGON_KEY}"
        bars = requests.get(url, timeout=10).json().get('results', [])
        if len(bars) < 10: return None
        pv = sum(b['c']*b['v'] for b in bars)
        vv = sum(b['v'] for b in bars)
        vwap = pv/vv if vv else bars[0]['c']
        return {
            'vwap': vwap,
            'last': bars[0]['c'],
            'prev': bars[1]['c'],
            'last_vol': bars[0]['v'],
            'prev_vol': bars[1]['v'],
            'bars': bars
        }
    except: return None

def get_score(sym, price, change, vol):
    try:
        f = get_float(sym)
        if f > 12000000: return -1, 0, "?"
        score = 0
        score += min(change * 2, 40)
        score += min(vol / 100000, 20)
        if f < 5000000: score += 30
        elif f < 10000000: score += 15

        vd = get_vwap_data(sym)
        if vd and abs(price - vd['vwap'])/vd['vwap']*100 <= 5:
            score += 20
        return score, f, f"{f/1000000:.1f}M" if f else "?"
    except: return 0, 0, "?"

def check_entry_signal(sym):
    """يرجع True اذا فيه اشارة دخول"""
    vd = get_vwap_data(sym)
    if not vd: return False, ""

    last = vd['last']
    vwap = vd['vwap']
    prev = vd['prev']
    last_vol = vd['last_vol']
    prev_vol = vd['prev_vol'] if vd['prev_vol'] else 1

    diff_pct = ((last - vwap)/vwap*100)
    is_near_vwap = -1.5 <= diff_pct <= 1.5 # لمس VWAP
    is_bullish = last > prev # شمعة خضراء
    is_vol = last_vol > prev_vol * 1.4 # فوليوم اعلى

    if is_near_vwap and is_bullish and is_vol:
        msg = f"اللمس: VWAP ${vwap:.2f} | السعر ${last:.2f} ({diff_pct:+.1f}%)\nفوليوم الارتداد: {last_vol/prev_vol:.1f}x"
        return True, msg
    return False, ""

def build_playbook():
    global daily_top3
    if not daily_candidates:
        send("📭 اليوم ما فيه اسهم تستاهل - لا تداول")
        return

    sorted_cands = sorted(daily_candidates, key=lambda x: x['score'], reverse=True)[:3]
    daily_top3 = {c['sym']: {'float_txt': c['float_txt'], 'entered': False, 'entry_price': 0} for c in sorted_cands}

    msg = f"📘 *PLAYBOOK اليوم {datetime.now(pytz.timezone('Asia/Riyadh')).strftime('%m/%d')}*\nفحصنا {len(daily_candidates)} سهم - افضل 3:\n\n"
    for i, c in enumerate(sorted_cands, 1):
        msg += f"{i}. *{c['sym']}* - ${c['price']:.2f} (+{c['change']:.1f}%)\n Float: {c['float_txt']} Vol: {c['vol']/1000:.0f}K\n"
    msg += "\n⏳ *انتظر اشارة الدخول 🟢*\nالبوت بيراقب لمسة VWAP"
    send(msg)

send("✅ *بوت V6 اشتغل - مع اشارة دخول وخروج*\n11ص-11:15 تجميع\n11:15 PlayBook\nبعدها: 🟢 دخول + 💰 بيع")

while True:
    try:
        tz = pytz.timezone('Asia/Riyadh')
        now = datetime.now(tz)

        if not is_allowed():
            if now.hour == 3 and now.minute < 5:
                daily_candidates.clear()
                daily_top3.clear()
                sent_events.clear()
            time.sleep(60)
            continue

        # 1. تجميع 11:00-11:15
        if 11 <= now.hour < 12 and now.minute < 15:
            try:
                gainers = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}", timeout=15).json().get('tickers', [])[:40]
                for t in gainers:
                    sym = t.get('ticker')
                    if not sym or len(sym)>5: continue
                    if any(c['sym']==sym for c in daily_candidates): continue
                    price = t.get('day',{}).get('c',0)
                    vol = t.get('day',{}).get('v',0)
                    change = t.get('todaysChangePerc',0)
                    if not (1.5 < price < 8 and 10 <= change < 60 and vol > 250000): continue
                    score, fshares, ftxt = get_score(sym, price, change, vol)
                    if score < 25: continue
                    daily_candidates.append({'sym': sym, 'price': price, 'change': change, 'vol': vol, 'score': score, 'float_txt': ftxt})
                    time.sleep(1)
            except: pass

        # 2. PlayBook 11:15
        if now.hour == 11 and now.minute == 15 and playbook_sent_date!= str(now.date()):
            build_playbook()
            playbook_sent_date = str(now.date())

        # 3. مراقبة اشارات دخول وخروج
        if daily_top3 and (now.hour > 11 or (now.hour==11 and now.minute>=15)):
            try:
                gainers = requests.get(f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers?apiKey={POLYGON_KEY}", timeout=15).json().get('tickers', [])[:60]
                gain_map = {t.get('ticker'): t for t in gainers}

                for sym in list(daily_top3.keys()):
                    if sym not in gain_map: continue
                    t = gain_map[sym]
                    price = t.get('day',{}).get('c',0)
                    change = t.get('todaysChangePerc',0)

                    # اشارة دخول
                    if not daily_top3[sym]['entered']:
                        is_entry, detail = check_entry_signal(sym)
                        key = f"entry_{sym}_{now.strftime('%H%M')}"
                        if is_entry and key not in sent_events:
                            daily_top3[sym]['entered'] = True
                            daily_top3[sym]['entry_price'] = price
                            send(f"🟢 *دخول {sym} الان*\n{detail}\nالسعر: ${price:.2f} (+{change:.1f}%)\nالوقف: تحت VWAP بـ 2%\n[📈 الشارت](https://www.tradingview.com/chart/?symbol={sym})")
                            sent_events.add(key)

                    # اشارات خروج
                    else:
                        entry = daily_top3[sym]['entry_price']
                        profit = ((price - entry)/entry*100) if entry else 0

                        if profit >= 35 and f"sell_half_{sym}" not in sent_events:
                            send(f"💰 *بيع نصف {sym} الان*\nدخول: ${entry:.2f} | الان: ${price:.2f} (+{profit:.1f}%)\nبعت 50% - خلي الباقي لـ 50%+")
                            sent_events.add(f"sell_half_{sym}")

                        if change >= 45 and f"rocket_{sym}" not in sent_events:
                            send(f"🚀 *{sym} حقق الهدف 50% تقريبا*\nالان: +{change:.1f}% (${price:.2f})\nاذا ما بعت النصف، بيع الان")
                            sent_events.add(f"rocket_{sym}")

                        if profit <= -5 and f"stop_{sym}" not in sent_events:
                            send(f"⛔ *وقف خسارة {sym}*\nدخول: ${entry:.2f} | الان: ${price:.2f} ({profit:.1f}%)\nاطلع - لمس VWAP فشل")
                            sent_events.add(f"stop_{sym}")

            except Exception as e:
                print(e)

        time.sleep(45)

    except Exception as e:
        print(e)
        time.sleep(15)
