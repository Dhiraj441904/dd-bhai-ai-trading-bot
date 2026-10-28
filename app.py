import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timezone

st.set_page_config(page_title="DD Bhai AI Trading Lab", layout="wide")
st.title("DD Bhai AI Trading Lab")
st.caption("V2 • Multi-market research • $500 virtual account • Paper trading only")

st.warning(
    "Research tool only. This version fetches public market data where available; "
    "it does not connect to Vantage or place live orders. Data providers may delay, omit, "
    "or revise data. No return is guaranteed."
)

MARKETS = {
    "Gold (XAUUSD proxy)": {"ticker": "XAUUSD=X", "group": "Gold", "intervals": ["1h", "1d"], "note": "Yahoo Finance symbol proxy; not guaranteed to match Vantage quotes."},
    "EUR/USD": {"ticker": "EURUSD=X", "group": "Forex", "intervals": ["1h", "1d"], "note": "Public-data proxy; broker spread/execution not included."},
    "GBP/USD": {"ticker": "GBPUSD=X", "group": "Forex", "intervals": ["1h", "1d"], "note": "Public-data proxy; broker spread/execution not included."},
    "USD/JPY": {"ticker": "JPY=X", "group": "Forex", "intervals": ["1h", "1d"], "note": "Public-data proxy; verify quote convention."},
    "Bitcoin (BTC/USD)": {"ticker": "BTC-USD", "group": "Crypto", "intervals": ["1h", "1d"], "note": "Public crypto price proxy; not exchange-specific execution data."},
    "Ethereum (ETH/USD)": {"ticker": "ETH-USD", "group": "Crypto", "intervals": ["1h", "1d"], "note": "Public crypto price proxy; not exchange-specific execution data."},
}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(ticker, period, interval):
    import yfinance as yf
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False, threads=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()
    df = df[required + (["volume"] if "volume" in df.columns else [])].copy()
    df = df.reset_index()
    dtcol = "datetime" if "datetime" in df.columns else ("date" if "date" in df.columns else df.columns[0])
    df = df.rename(columns={dtcol: "time"})
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    for c in required:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df

def add_indicators(df):
    d = df.copy()
    d["ema20"] = d["close"].ewm(span=20, adjust=False).mean()
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean()
    d["ema200"] = d["close"].ewm(span=200, adjust=False).mean()
    d["ret1"] = d["close"].pct_change()
    d["vol20"] = d["ret1"].rolling(20).std()
    d["prior_high20"] = d["high"].shift(1).rolling(20).max()
    d["prior_low20"] = d["low"].shift(1).rolling(20).min()
    delta = d["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi"] = 100 - (100 / (1 + rs))
    tr = pd.concat([
        d["high"] - d["low"],
        (d["high"] - d["close"].shift()).abs(),
        (d["low"] - d["close"].shift()).abs()
    ], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean()
    return d

def score_latest(d):
    row = d.iloc[-1]
    long_trend = row["ema20"] > row["ema50"] > row["ema200"]
    short_trend = row["ema20"] < row["ema50"] < row["ema200"]
    long_break = pd.notna(row["prior_high20"]) and row["close"] > row["prior_high20"]
    short_break = pd.notna(row["prior_low20"]) and row["close"] < row["prior_low20"]
    long_mr = pd.notna(row["rsi"]) and row["rsi"] < 28
    short_mr = pd.notna(row["rsi"]) and row["rsi"] > 72
    long_score = 35*int(long_trend) + 35*int(long_break) + 15*int(long_mr)
    short_score = 35*int(short_trend) + 35*int(short_break) + 15*int(short_mr)
    score = max(long_score, short_score)
    if long_score >= 35 and long_score >= short_score:
        signal = "BUY candidate"
        direction = 1
    elif short_score >= 35:
        signal = "SELL candidate"
        direction = -1
    else:
        signal = "NO TRADE"
        direction = 0
    atr = row["atr14"] if pd.notna(row["atr14"]) and row["atr14"] > 0 else row["close"] * 0.005
    stop = row["close"] - direction * 1.5 * atr if direction else np.nan
    target = row["close"] + direction * 2.25 * atr if direction else np.nan
    return {
        "signal": signal, "direction": direction, "score": int(score),
        "close": float(row["close"]), "rsi": float(row["rsi"]) if pd.notna(row["rsi"]) else np.nan,
        "atr": float(atr), "stop": float(stop) if pd.notna(stop) else np.nan,
        "target": float(target) if pd.notna(target) else np.nan,
        "time": row["time"]
    }

def backtest(d, starting_balance, risk_pct, cost_bps):
    # Educational candle-level simulation: next-bar entry, fixed ATR stop/target.
    # If both stop and target touched in one candle, assume stop first (conservative).
    d = d.copy().reset_index(drop=True)
    equity = float(starting_balance)
    peak = equity
    max_dd = 0.0
    trades = []
    equity_rows = []
    pos = 0
    entry = stop = target = risk_cash = 0.0
    entry_idx = None
    for i in range(220, len(d)-1):
        row = d.iloc[i]
        if pos:
            hit_stop = row["low"] <= stop if pos == 1 else row["high"] >= stop
            hit_target = row["high"] >= target if pos == 1 else row["low"] <= target
            if hit_stop or hit_target:
                exit_px = stop if hit_stop else target
                pct = (exit_px-entry)/entry*pos - cost_bps/10000
                stop_pct = abs(stop-entry)/entry
                pnl = risk_cash * pct / max(stop_pct, 1e-9)
                equity += pnl
                trades.append({"entry_time": d.loc[entry_idx, "time"], "exit_time": row["time"],
                               "side": "BUY" if pos == 1 else "SELL", "entry": entry,
                               "exit": exit_px, "pnl_usd": pnl, "balance": equity,
                               "exit_reason": "Stop" if hit_stop else "Target"})
                pos = 0
        if not pos:
            # Use indicators available at candle close; entry on next bar open.
            latest = score_latest(d.iloc[:i+1])
            if latest["direction"] != 0 and latest["score"] >= 35:
                pos = latest["direction"]
                entry = float(d.loc[i+1, "open"])
                atr = latest["atr"]
                stop = entry - pos*1.5*atr
                target = entry + pos*2.25*atr
                risk_cash = equity*risk_pct/100
                entry_idx = i+1
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak-equity)/peak if peak > 0 else 0)
        equity_rows.append({"time": row["time"], "equity": equity, "drawdown_pct": 100*max_dd})
    return pd.DataFrame(trades), pd.DataFrame(equity_rows), equity, max_dd

with st.sidebar:
    st.header("Settings")
    starting = st.number_input("Virtual starting balance ($)", min_value=50.0, max_value=100000.0, value=500.0, step=50.0)
    timeframe = st.selectbox("Candle interval", ["1h", "1d"], index=0)
    period = st.selectbox("Historical period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
    risk_pct = st.slider("Risk budget per trade (%)", 0.1, 3.0, 0.5, 0.1)
    cost_bps = st.slider("Assumed round-trip costs (bps)", 0.0, 30.0, 8.0, 0.5)
    st.caption("Cost assumption is a rough simulation input, not Vantage's actual spread/commission.")

if st.button("Refresh public market data"):
    st.cache_data.clear()

rows = []
frames = {}
with st.spinner("Fetching public market data..."):
    for name, cfg in MARKETS.items():
        try:
            df = fetch_data(cfg["ticker"], period, timeframe)
            if len(df) >= 220:
                ind = add_indicators(df)
                sig = score_latest(ind)
                rows.append({
                    "Market": name, "Type": cfg["group"], "Signal": sig["signal"],
                    "Score": sig["score"], "Last price": sig["close"],
                    "RSI": sig["rsi"], "Latest candle (UTC)": str(sig["time"]),
                    "Data bars": len(ind)
                })
                frames[name] = (ind, sig, cfg)
            else:
                rows.append({"Market": name, "Type": cfg["group"], "Signal": "DATA UNAVAILABLE",
                             "Score": 0, "Last price": np.nan, "RSI": np.nan,
                             "Latest candle (UTC)": "Not enough bars / provider unavailable",
                             "Data bars": len(df)})
        except Exception as e:
            rows.append({"Market": name, "Type": cfg["group"], "Signal": "DATA ERROR",
                         "Score": 0, "Last price": np.nan, "RSI": np.nan,
                         "Latest candle (UTC)": "Fetch failed; retry later",
                         "Data bars": 0})

st.subheader("Multi-market signal scanner")
scanner = pd.DataFrame(rows)
if not scanner.empty:
    scanner = scanner.sort_values(["Score", "Market"], ascending=[False, True])
    st.dataframe(scanner, use_container_width=True, hide_index=True)

available = list(frames.keys())
if available:
    selected = st.selectbox("Market details", available)
    d, sig, cfg = frames[selected]
    st.caption(cfg["note"])
    a, b, c, e = st.columns(4)
    a.metric("Latest price", f"{sig['close']:.6f}")
    b.metric("Rule score", f"{sig['score']}/85")
    c.metric("Signal", sig["signal"])
    e.metric("RSI", f"{sig['rsi']:.1f}" if pd.notna(sig["rsi"]) else "N/A")
    st.caption(f"Last candle UTC: {sig['time']} • Provider: Yahoo Finance public data • Not Vantage executable pricing.")
    chart = d[["time", "close", "ema20", "ema50", "ema200"]].melt(id_vars="time", var_name="series", value_name="price")
    st.plotly_chart(px.line(chart, x="time", y="price", color="series", title=f"{selected} — public data and indicators"), use_container_width=True)
    st.write("**Illustrative levels**")
    st.write({
        "Signal": sig["signal"],
        "Reference price": round(sig["close"], 6),
        "Stop reference": round(sig["stop"], 6) if pd.notna(sig["stop"]) else None,
        "Target reference": round(sig["target"], 6) if pd.notna(sig["target"]) else None,
        "Note": "These are research references, not orders or personalized financial advice."
    })
    st.subheader("Historical simulation (simplified)")
    trades, eq, final_eq, max_dd = backtest(d, starting, risk_pct, cost_bps)
    gross_profit = trades.loc[trades.pnl_usd > 0, "pnl_usd"].sum() if len(trades) else 0.0
    gross_loss = -trades.loc[trades.pnl_usd < 0, "pnl_usd"].sum() if len(trades) else 0.0
    pf = gross_profit/gross_loss if gross_loss > 0 else np.nan
    x1, x2, x3, x4 = st.columns(4)
    x1.metric("Closed trades", len(trades))
    x2.metric("Ending balance", f"${final_eq:,.2f}", f"{(final_eq/starting-1)*100:+.2f}%")
    x3.metric("Profit factor", f"{pf:.2f}" if pd.notna(pf) else "N/A")
    x4.metric("Max drawdown", f"{max_dd*100:.2f}%")
    if not eq.empty:
        st.plotly_chart(px.line(eq, x="time", y="equity", title="Simplified historical simulation equity"), use_container_width=True)
    if not trades.empty:
        st.dataframe(trades.tail(100), use_container_width=True, hide_index=True)
    else:
        st.info("No trades triggered for this sample. Do not force trades just to increase activity.")
else:
    st.error("No market data loaded. Try a daily interval, shorter/longer period, or refresh later. Public providers can throttle requests.")

st.subheader("Important limitations")
st.markdown("""
- Public Yahoo Finance data is not a Vantage feed and may be delayed, incomplete, or unavailable.
- Gold/Forex quote symbols are proxies; do not assume prices, spread, contract size, margin, swaps, or fills match your Vantage account.
- This is a rule-based research scanner, not a trained AI model and not an order-execution system.
- Backtest is simplified and does not model broker-specific contract sizes, tick values, swaps, margin calls, partial fills, or all intrabar paths.
- 30,000% monthly return is not promised; extreme leverage can rapidly wipe out an account.
- Use paper trading only until data quality, backtesting, and risk controls have been independently validated.
""")
