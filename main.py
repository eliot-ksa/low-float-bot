//@version=5
indicator("Breakout Signals (Donchian + 200 EMA + Volume + ATR) Easier_stock", overlay=true, max_labels_count=500)

// ─────────────────────────────────────────────────────────────
// Signal toggles
enableBuy  = input.bool(true,  "Enable BUY Signals")
enableSell = input.bool(true,  "Enable SELL Signals")

// ─────────────────────────────────────────────────────────────
// Breakout settings
len            = input.int(20,  "Donchian Lookback", minval=2)
useCloseLevels = input.bool(false, "Use Close for Levels (vs High/Low)")
atrLen         = input.int(14,  "ATR Length", minval=1)
atrMult        = input.float(0.10, "Breakout ATR Buffer Mult", step=0.05)
confirmClose   = input.bool(true, "Require Bar Close Beyond Level")
cooldownBars   = input.int(0, "Cooldown Bars Between Signals", minval=0)

// ─────────────────────────────────────────────────────────────
// Volume filter (optional)
useVolFilter = input.bool(false, "Use Volume Filter")
volLen       = input.int(30, "Volume SMA Length", minval=1)
volMult      = input.float(1.2, "Volume Multiplier", step=0.1)

// ─────────────────────────────────────────────────────────────
// EMA trend filter (optional)
useTrendFilter = input.bool(false, "Use EMA Trend Filter")
emaLen         = input.int(200, "EMA Length", minval=1)

// ─────────────────────────────────────────────────────────────
// Stop settings (ATR-based)
stopMode     = input.string("Fixed From Entry", "Stop Mode", options=["Fixed From Entry", "Chandelier"])
stopAtrMult  = input.float(2.0, "Stop ATR Mult", step=0.25)
stopLookback = input.int(22, "Chandelier Lookback", minval=1)

// ─────────────────────────────────────────────────────────────
// Donchian levels (IMPORTANT: previous bars only)
srcHigh = useCloseLevels ? close : high
srcLow  = useCloseLevels ? close : low

upper = ta.highest(srcHigh[1], len)
lower = ta.lowest(srcLow[1], len)

atr = ta.atr(atrLen)
buf = atr * atrMult

// Filters
volOk = not useVolFilter or (volume > ta.sma(volume, volLen) * volMult)

ema = ta.ema(close, emaLen)
trendOkLong  = not useTrendFilter or close > ema
trendOkShort = not useTrendFilter or close < ema

// Breakout conditions
longBreak  = confirmClose ? (close > upper + buf) : (high > upper + buf)
shortBreak = confirmClose ? (close < lower - buf) : (low < lower - buf)

// Cooldown to reduce repeated signals
var int lastSignalBar = na
canSignal = na(lastSignalBar) or (bar_index - lastSignalBar > cooldownBars)

// Signals (respect toggles + filters)
buySignal  = enableBuy  and canSignal and volOk and trendOkLong  and longBreak
sellSignal = enableSell and canSignal and volOk and trendOkShort and shortBreak

if buySignal or sellSignal
    lastSignalBar := bar_index

// ─────────────────────────────────────────────────────────────
// Stop prices computed ONLY for the signal candle
longStopFixed  = close - stopAtrMult * atr
shortStopFixed = close + stopAtrMult * atr

longStopChand  = ta.highest(high, stopLookback) - stopAtrMult * atr
shortStopChand = ta.lowest(low, stopLookback)  + stopAtrMult * atr

buyStopPrice  = stopMode == "Chandelier" ? longStopChand  : longStopFixed
sellStopPrice = stopMode == "Chandelier" ? shortStopChand : shortStopFixed

// Only show dots on the signal candle
buyStopDot  = buySignal  ? buyStopPrice  : na
sellStopDot = sellSignal ? sellStopPrice : na

// ─────────────────────────────────────────────────────────────
// Plotting
plot(upper, "Upper (Prev Donchian)", color=color.new(color.green, 0), linewidth=2)
plot(lower, "Lower (Prev Donchian)", color=color.new(color.red, 0), linewidth=2)
plot(useTrendFilter ? ema : na, "EMA", color=color.new(color.orange, 0), linewidth=2)

plotshape(buySignal,  title="BUY",  style=shape.labelup,   text="BUY",
     color=color.new(color.green, 0), textcolor=color.white,
     location=location.belowbar, size=size.tiny)

plotshape(sellSignal, title="SELL", style=shape.labeldown, text="SELL",
     color=color.new(color.red, 0), textcolor=color.white,
     location=location.abovebar, size=size.tiny)

// ✅ ATR Stop dots ONLY on the signal candle
plot(buyStopDot,  title="BUY Stop Dot",  style=plot.style_circles, linewidth=4, color=color.new(color.yellow, 0))
plot(sellStopDot, title="SELL Stop Dot", style=plot.style_circles, linewidth=4, color=color.new(color.yellow, 0))

// Alerts
alertcondition(buySignal,  "Breakout BUY",  "BUY breakout signal")
alertcondition(sellSignal, "Breakout SELL", "SELL breakout signal")
