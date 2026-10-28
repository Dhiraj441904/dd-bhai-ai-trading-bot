# DD Bhai AI Trading Lab V2

Mobile-friendly Streamlit research dashboard for Gold, Forex and Crypto public-market data.

## Current data sources
- Yahoo Finance via `yfinance` for XAUUSD proxy, EUR/USD, GBP/USD, USD/JPY, BTC/USD and ETH/USD.
- This is NOT a Vantage feed. Quote conventions, delays, history limits and availability may differ.
- No live orders are placed. No credentials or API keys are needed.

## Deploy
The repository root should contain:
- `app.py`
- `requirements.txt`
- `README.md`

On Streamlit Community Cloud, use repository `Dhiraj441904/dd-bhai-ai-trading-bot`, branch `main`, main file `app.py`. After replacing files in GitHub, Streamlit normally rebuilds the app.

## Safety and limitations
This is a rule-based research scanner, not a trained AI model and not a live trading bot. The backtest is simplified and not broker-specific. Do not assume any displayed level is executable at Vantage. A 30,000% monthly return cannot be promised; extreme leverage can rapidly wipe out capital. Paper test only.
