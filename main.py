import requests, os
from datetime import datetime, timedelta

POLYGON_KEY = os.getenv("POLYGON_KEY")

def get_day_gainers(date_str):
    # نجيب اكثر اسهم طارت في ذلك اليوم
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date_str}?adjusted=true&apiKey={POLYGON_KEY}"
    try:
        r = requests.get(url, timeout=20).json()
        results = r.get('results', [])
        # نفلتر 1.5-10$
        filtered = []
        for s in results:
            price = s.get('c',0)
            if 1.5 <= price <= 10 and s.get('v',0) > 500000:
                change = ((s['c']-s['o'])/s['o']*100) if s['o'] else 0
                if change > 15:
                    filtered.append({'T': s['T'], 'price': price, 'change': change})
        return sorted(filtered, key=lambda x: x['change'], reverse=True)[:5]
    except:
        return []

print("باك تست اخر 30 يوم - PlayBookTrades")
for i in range(30):
    d = (datetime.now() - timedelta(days=i+1)).strftime('%Y-%m-%d')
    # تجاهل ويكند
    if datetime.strptime(d, '%Y-%m-%d').weekday() >=5: continue
    gainers = get_day_gainers(d)
    if gainers:
        print(f"\n{d} - لقى {len(gainers)}:")
        for g in gainers:
            print(f"  {g['T']} +{g['change']:.1f}% ${g['price']:.2f}")
    else:
        print(f"{d} - ما فيه")
