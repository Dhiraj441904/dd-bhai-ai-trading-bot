# DD Bhai AI Trading Lab V3

Multi-market public-data research dashboard for Gold, Forex, and Crypto.

## Features
- All-market scanner and rule scores.
- Per-market holdout win rate, trade count, return, profit factor, and max drawdown.
- Chronological 70%/30% train/holdout reporting.
- Yahoo Finance data via yfinance.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload `app.py`, `requirements.txt`, and `README.md` to the root of your GitHub repository and commit. Reboot the Streamlit app if needed.

## Limitations
This is rule-based research software, not a trained AI model. It does not connect to Vantage or place orders. Yahoo Finance data may be missing or differ from broker execution prices. The backtest is simplified and does not model broker-specific contract sizes, swaps, margin, partial fills, or exact slippage. No win rate or return is guaranteed. Paper test before considering real-money use.
