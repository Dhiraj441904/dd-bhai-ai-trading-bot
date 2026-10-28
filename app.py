import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="DD Bhai AI Trading Lab", layout="wide")
st.title("DD Bhai AI Trading Lab")
st.caption("Version 1 • Multi-market signal research • $500 virtual account • NO live orders")

st.warning(
    "Research simulator only. This starter uses synthetic sample prices, not live Vantage prices. "
    "It cannot place orders. Extreme-return targets are not guaranteed and can imply account wipeout risk."
)

with st.sidebar:
    st.header("Simulation settings")
    capital = st.number_input("Virtual starting balance ($)", min_value=50.0, max_value=100000.0, value=500.0, step=50.0)
    bars = st.slider("Synthetic candles", 300, 3000, 1200, 100)
    seed = st.number_input("Random seed", min_value=1, max_value=99999, value=42)
    risk_pct = st.slider("Risk budget per trade (%)", 0.1, 5.0, 0.5, 0.1)
    fee_bps = st.slider("Assumed round-trip costs (bps)", 0.0, 20.0, 4.0, 0.5)
    market = st.selectbox("Sample market", ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSDT", "ETHUSDT"])
    st.caption("Synthetic prices are only for checking that the software runs.")

@st.cache_data
def make_data(n, seed, market):
    rng = np.random.default_rng(int(seed))
    if market == "XAUUSD":
        start, vol, drift = 2300.0, 0.0030, 0.00002
    elif market in ("EURUSD", "GBPUSD", "USDJPY"):
        start, vol, drift = (1.08, 0.0012, 0.000005) if market == "EURUSD" else ((1.27, 0.0015, 0.000004) if market == "GBPUSD" else (150.0, 0.0012, 0.000003))
    else:
        start, vol, drift = (65000.0, 0.012, 0.00008) if market == "BTCUSDT" else (3200.0, 0.014, 0.00007)
    # Synthetic regime shifts: illustrative only, not a market forecast.
    shocks = rng.normal(drift, vol, n)
    for k in range(4, n, max(40, n // 8)):
        shocks[k:k + max(10, n // 30)] += rng.normal(0, vol * 0.9)
    close = start * np.exp(np.cumsum(shocks))
    df = pd.DataFrame({"close": close})
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0])
    wiggle = np.abs(rng.normal(vol, vol * 0.4, n))
    df["high"] = np.maximum(df["open"], df["close"]) * (1 + wiggle)
    df["low"] = np.minimum(df["open"], df["close"]) * (1 - wiggle)
    df["volume"] = rng.lognormal(8, 0.5, n)
    return df

def indicators(df):
    d = df.copy()
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean()
    d["ema200"] = d["close"].ewm(span=200, adjust=False).mean()
    d["ret1"] = d["close"].pct_change()
    d["vol20"] = d["ret1"].rolling(20).std()
    d["hi20"] = d["high"].shift(1).rolling(20).max()
    d["lo20"] = d["low"].shift(1).rolling(20).min()
    delta = d["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))
    return d

def add_signals(d):
    d = d.copy()
    trend_long = (d["ema20"] > d["ema50"]) & (d["ema50"] > d["ema200"])
    trend_short = (d["ema20"] < d["ema50"]) & (d["ema50"] < d["ema200"])
    breakout_long = d["close"] > d["hi20"]
    breakout_short = d["close"] < d["lo20"]
    # Basic mean-reversion candidate, deliberately gated away from strong trend.
    mean_long = (d["rsi"] < 28) & (d["ema20"] < d["ema50"])
    mean_short = (d["rsi"] > 72) & (d["ema20"] > d["ema50"])
    score_long = 30*trend_long.astype(int) + 25*breakout_long.astype(int) + 15*mean_long.astype(int)
    score_short = 30*trend_short.astype(int) + 25*breakout_short.astype(int) + 15*mean_short.astype(int)
    d["signal"] = np.where(score_long >= 30, 1, np.where(score_short >= 30, -1, 0))
    d["score"] = np.maximum(score_long, score_short)
    d["setup"] = np.select(
        [breakout_long | breakout_short, trend_long | trend_short, mean_long | mean_short],
        ["Breakout", "Trend", "Mean reversion"],
        default="No trade"
    )
    return d

def simulate(d, starting, risk_pct, fee_bps):
    d = d.copy().reset_index(drop=True)
    equity = float(starting)
    peak = equity
    max_dd = 0.0
    position = 0
    entry = 0.0
    stop = 0.0
    target = 0.0
    risk_cash = 0.0
    trades = []
    eq = []
    # Conservative toy simulator: one position at a time, next-bar entry,
    # fixed ATR-like stop distance, no leverage and no live execution.
    d["range_proxy"] = (d["high"] - d["low"]).rolling(14).mean()
    for i in range(1, len(d)-1):
        row = d.iloc[i]
        next_open = float(d.iloc[i+1]["open"])
        if position != 0:
            hit_stop = (row["low"] <= stop) if position == 1 else (row["high"] >= stop)
            hit_target = (row["high"] >= target) if position == 1 else (row["low"] <= target)
            # If both are touched in one candle, assume the stop happened first.
            if hit_stop or hit_target:
                exit_price = stop if hit_stop else target
                gross_pct = (exit_price - entry) / entry * position
                net_pct = gross_pct - fee_bps / 10000
                pnl = risk_cash * (net_pct / max(abs((stop-entry)/entry), 1e-6))
                equity += pnl
                trades.append({"entry_bar": entry_i, "exit_bar": i, "side": "BUY" if position == 1 else "SELL",
                               "entry": entry, "exit": exit_price, "PnL": pnl, "equity": equity,
                               "exit_reason": "Stop" if hit_stop else "Target"})
                position = 0
        if position == 0 and int(d.iloc[i]["signal"]) != 0 and int(d.iloc[i]["score"]) >= 30:
            px = next_open
            dist = max(float(row["range_proxy"]) * 1.5 if pd.notna(row["range_proxy"]) else px*0.005, px*0.001)
            position = int(d.iloc[i]["signal"])
            entry = px
            stop = px - dist if position == 1 else px + dist
            target = px + 1.5*dist if position == 1 else px - 1.5*dist
            risk_cash = equity * risk_pct / 100
            entry_i = i+1
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak if peak > 0 else 0)
        eq.append({"bar": i, "equity": equity, "drawdown_pct": 100*max_dd})
    if position != 0:
        final_px = float(d.iloc[-1]["close"])
        gross_pct = (final_px-entry)/entry*position
        net_pct = gross_pct-fee_bps/10000
        pnl = risk_cash*(net_pct/max(abs((stop-entry)/entry), 1e-6))
        equity += pnl
        trades.append({"entry_bar": entry_i, "exit_bar": len(d)-1, "side": "BUY" if position == 1 else "SELL",
                       "entry": entry, "exit": final_px, "PnL": pnl, "equity": equity, "exit_reason": "End of sample"})
    t = pd.DataFrame(trades)
    e = pd.DataFrame(eq)
    return t, e, equity, max_dd

raw = make_data(int(bars), int(seed), market)
data = add_signals(indicators(raw))
trades, equity_curve, final_equity, max_dd = simulate(data, capital, risk_pct, fee_bps)
last = data.iloc[-1]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest illustrative price", f"{last['close']:.5f}")
c2.metric("Signal", {1:"BUY candidate", -1:"SELL candidate", 0:"NO TRADE"}[int(last["signal"])])
c3.metric("Rule score", f"{int(last['score'])}/100")
c4.metric("Simulated ending balance", f"${final_equity:,.2f}", f"{(final_equity/capital-1)*100:+.2f}%")

st.subheader("Price and indicators")
chart_data = data[["close", "ema20", "ema50", "ema200"]].reset_index(names="bar").melt(id_vars="bar", var_name="series", value_name="price")
st.plotly_chart(px.line(chart_data, x="bar", y="price", color="series", title=f"{market} — synthetic sample only"), use_container_width=True)

st.subheader("Backtest summary")
win_rate = (trades["PnL"] > 0).mean()*100 if len(trades) else 0.0
gross_profit = trades.loc[trades["PnL"] > 0, "PnL"].sum() if len(trades) else 0.0
gross_loss = -trades.loc[trades["PnL"] < 0, "PnL"].sum() if len(trades) else 0.0
pf = gross_profit/gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Closed trades", len(trades))
m2.metric("Win rate", f"{win_rate:.1f}%")
m3.metric("Profit factor", f"{pf:.2f}" if np.isfinite(pf) else "∞")
m4.metric("Max drawdown", f"{max_dd*100:.2f}%")
st.caption("This is a starter simulator, not a validated backtest: simplified fills, synthetic prices, and no broker-specific contract/margin model.")
if len(equity_curve):
    st.plotly_chart(px.line(equity_curve, x="bar", y="equity", title="Illustrative simulated equity"), use_container_width=True)
if len(trades):
    st.dataframe(trades.tail(100), use_container_width=True)
else:
    st.info("No trades triggered in this sample. That is a valid outcome; do not force trades to create activity.")

st.subheader("Next development steps")
st.markdown("""
1. Replace synthetic candles with verified historical data from your intended sources.
2. Add a chronological train/validation/test split and walk-forward evaluation.
3. Model broker-specific contract sizes, spread, swaps, slippage, stop execution and margin.
4. Add separate crypto connector and instrument-specific settings.
5. Run paper trading only. This app has no live-order connection.
""")
