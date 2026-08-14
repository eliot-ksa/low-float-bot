import os, requests, time
from datetime import datetime, timedelta

POLYGON_KEY = os.getenv("POLYGON_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send(m):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown"}, timeout=15)

def get_float(sym):
    try:
        r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{sym}?apiKey={POLYGON_KEY}", timeout=8).json()
        return r.get('results',{}).get('share_class_shares_outstanding', 0)
    except: return 0

send("🧪 *بدأ باك تست 30 يوم - PlayBookTrades*\nانتظر 3 دقايق...")

report = f"📊 *باك تست 30 يوم - لو البوت كان شغال*\n\n"
total_days = 0
trade_days = 0

for i in range(1, 31):
    d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
    if datetime.strptime(d, '%Y-%m-%d').weekday() >=5: continue
    total_days += 1
    
    try:
        url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{d}?adjusted=true&apiKey={POLYGON_KEY}"
        res = requests.get(url, timeout=20).json()
        results = res.get('results', [])
        
        day_cands = []
        for s in results:
            price = s.get('c',0)
            vol = s.get('v',0)
            if not (1.5 <= price <= 10 and vol > 400000): continue
            o = s.get('o',0)
            if not o: continue
            change = ((price - o)/o*100)
            if change < 15: continue
            
            sym = s.get('T','')
            if len(sym) > 5: continue
            
            f = get_float(sym)
            if f !=0 and f > 10000000: continue
            
            day_cands.append({'sym': sym, 'change': change, 'price': price, 'float': f})
        
        if day_cands:
            trade_days += 1
            top = sorted(day_cands, key=lambda x: x['change'], reverse=True)[:2]
            report += f"*{d}* - {len(day_cands)} سهم\n"
            for c in top:
                report += f"  {c['sym']} +{c['change']:.1f}% ${c['price']:.2f} Float {c['float']/1000000:.1f}M\n"
            report += "\n"
        else:
            report += f"{d} - لا يوجد\n\n"
            
        time.sleep(0.3) # عشان لا ننحظر
        
    except Exception as e:
        report += f"{d} - خطأ {e}\n\n"

report += f"\nالخلاصة:\n{trade_days}/{total_days} يوم كان فيه تداول\n{total_days-trade_days} يوم ما فيه (طبيعي في PlayBookTrades)"
send(report)
print(report)
