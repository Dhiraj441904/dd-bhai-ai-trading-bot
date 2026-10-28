# DD Bhai AI Trading Lab — Version 1

## What this is
A mobile-friendly Streamlit starter for multi-market signal research and paper/backtest experimentation. It currently uses **synthetic sample prices** so you can verify that the app runs. It does not connect to Vantage, does not use live market data, and cannot place real orders.

## Run on Android (browser-only workflow)
1. Open Google Colab: https://colab.research.google.com/
2. Create a new notebook.
3. Upload this ZIP to Colab, then extract it:
   ```python
   import zipfile
   with zipfile.ZipFile('/content/dd_bhai_ai_trading_bot_v1.zip') as z:
       z.extractall('/content/dd_bhai_ai_trading_bot_v1')
   ```
   If the ZIP upload path differs, update the path in the code.
4. Install dependencies in a notebook cell:
   ```python
   %pip install -r /content/dd_bhai_ai_trading_bot_v1/requirements.txt
   ```
5. Streamlit needs a web server process; easiest stable route is deploying the files through a GitHub repository to Streamlit Community Cloud. See:
   https://docs.streamlit.io/deploy/streamlit-community-cloud
6. Put `app.py` and `requirements.txt` in the repository root. In Streamlit Community Cloud, create an app and select `app.py` as the entrypoint.
7. Open the resulting app URL on your Android phone.

## Important Colab limitation
Colab runtimes can disconnect or terminate and are not a reliable 24/7 trading host. Use it for experimentation only, not unattended execution.

## Vantage integration
The Vantage mobile app alone does not provide a direct Python trading API. First check whether your account is MT4 or MT5 and whether you can create a demo MT5 account. Automated MT5 Expert Advisors run on a desktop terminal; continuous automation generally needs a compatible Windows VPS/terminal or another supported integration. Do not provide passwords or API keys to this starter app.

## Planned upgrades
- Import verified historical CSV candle data.
- Correct chronological walk-forward backtesting.
- Broker-specific contract/tick-value, spread, swap and margin model.
- Separate crypto exchange market-data connector.
- Model calibration and ranking evaluation.
- Paper-trade event log and risk kill switches.

## Risk
A 30,000% monthly return cannot be promised. Extreme leverage can rapidly liquidate an account. Keep all tests virtual until the data, simulator and risk controls have been independently checked.
