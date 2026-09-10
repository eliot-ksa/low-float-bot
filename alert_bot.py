"""
بوت تنبيهات اختراق Donchian + ATR لأسهم أمريكية — نسخة بايثون من مؤشر TradingView
يشتغل كل 15 دقيقة عبر GitHub Actions ويرسل تنبيه تلغرام عند تحقق شرط BUY/SELL
(نفس منطق: Donchian breakout + ATR buffer + Require Bar Close Beyond Level)
"""

import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
import requests

from config import (
    SYMBOLS, DONCHIAN_LEN, ATR_LEN, ATR_MULT, STOP_ATR_MULT,
    INTERVAL, INTERVAL_MINUTES, STATE_FILE,
)


def compute_atr(df: pd.DataFrame, length: int) -> pd.Series:
    """تقريب لـ ta.atr في Pine (Wilder's RMA)."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def is_market_hours() -> bool:
    ny = ZoneInfo("America/New_York")
    now = datetime.now(ny)
    if now.weekday() >= 5:  # سبت / أحد
        return False
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= now <= close_t


def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        if not r.ok:
            print("خطأ إرسال تلغرام:", r.text)
    except Exception as e:
        print("استثناء أثناء إرسال تلغرام:", e)


def check_symbol(symbol: str, state: dict):
    try:
        df = yf.Ticker(symbol).history(period="5d", interval=INTERVAL)
    except Exception as e:
        print(f"خطأ بجلب بيانات {symbol}: {e}")
        return None

    if df is None or df.empty or len(df) < DONCHIAN_LEN + 5:
        return None

    # إسقاط الشمعة الحالية إذا لسا ما اكتملت
    tz = df.index.tz
    now = pd.Timestamp.now(tz=tz)
    if now < df.index[-1] + pd.Timedelta(minutes=INTERVAL_MINUTES):
        df = df.iloc[:-1]
    if df.empty:
        return None

    df["upper"] = df["High"].shift(1).rolling(DONCHIAN_LEN).max()
    df["lower"] = df["Low"].shift(1).rolling(DONCHIAN_LEN).min()
    df["atr"] = compute_atr(df, ATR_LEN)

    last = df.iloc[-1]
    if pd.isna(last["upper"]) or pd.isna(last["lower"]) or pd.isna(last["atr"]):
        return None

    buf = last["atr"] * ATR_MULT
    buy_signal = last["Close"] > (last["upper"] + buf)
    sell_signal = last["Close"] < (last["lower"] - buf)

    bar_time = df.index[-1].isoformat()
    sym_state = state.get(symbol, {})
    result = None

    if buy_signal and sym_state.get("buy") != bar_time:
        stop = last["Close"] - STOP_ATR_MULT * last["atr"]
        result = ("BUY", float(last["Close"]), float(stop), bar_time)
        sym_state["buy"] = bar_time
    elif sell_signal and sym_state.get("sell") != bar_time:
        stop = last["Close"] + STOP_ATR_MULT * last["atr"]
        result = ("SELL", float(last["Close"]), float(stop), bar_time)
        sym_state["sell"] = bar_time

    state[symbol] = sym_state
    return result


def main():
    if not is_market_hours():
        print("خارج ساعات تداول السوق الأمريكي - تخطي هذه الجولة")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit("لازم تضبط TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID كـ Secrets")

    state = load_state()
    found_any = False

    for symbol in SYMBOLS:
        result = check_symbol(symbol, state)
        if result:
            found_any = True
            direction, price, stop, bar_time = result
            emoji = "🟢" if direction == "BUY" else "🔴"
            msg = (
                f"{emoji} <b>{direction}</b> — {symbol}\n"
                f"السعر: {price:.2f}\n"
                f"وقف الخسارة المقترح: {stop:.2f}\n"
                f"الشمعة: {bar_time}"
            )
            send_telegram(token, chat_id, msg)
            print(msg)

    if not found_any:
        print("لا توجد إشارات هذه الجولة")

    save_state(state)


if __name__ == "__main__":
    main()
