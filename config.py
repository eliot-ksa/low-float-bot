# عدّل قائمة الأسهم اللي تبي تراقبها هنا
SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

# نفس إعدادات المؤشر بالضبط (القيم الافتراضية بالكود الأصلي)
DONCHIAN_LEN = 20        # len
ATR_LEN = 14             # atrLen
ATR_MULT = 0.10          # atrMult
STOP_ATR_MULT = 2.0      # stopAtrMult (Fixed From Entry)

# الفريم الزمني (يجب أن يطابق إعداد yfinance interval بالأسفل)
INTERVAL = "15m"
INTERVAL_MINUTES = 15

STATE_FILE = "state.json"
