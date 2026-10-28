import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title='DD Bhai AI Trading Lab V3', layout='wide')
st.title('DD Bhai AI Trading Lab — V3')
st.caption('Gold + Forex + Crypto | Multi-market scanner and holdout testing | Paper trading only')
st.warning('97% win rate and 30,000% monthly return are targets to test, not guarantees. This app does not connect to Vantage or place orders.')
MARKETS={'Gold (XAUUSD proxy)':('XAUUSD=X','Gold'),'EUR/USD':('EURUSD=X','Forex'),'GBP/USD':('GBPUSD=X','Forex'),'USD/JPY':('JPY=X','Forex'),'Bitcoin (BTC/USD)':('BTC-USD','Crypto'),'Ethereum (ETH/USD)':('ETH-USD','Crypto')}

@st.cache_data(ttl=300, show_spinner=False)
def fetch(ticker,period,interval):
    import yfinance as yf
    d=yf.download(ticker,period=period,interval=interval,auto_adjust=False,progress=False,threads=False)
    if d is None or d.empty: return pd.DataFrame()
    if isinstance(d.columns,pd.MultiIndex): d.columns=[c[0] for c in d.columns]
    d.columns=[str(c).lower().replace(' ','_') for c in d.columns]
    if not all(c in d.columns for c in ['open','high','low','close']): return pd.DataFrame()
    d=d.reset_index(); tc='datetime' if 'datetime' in d.columns else ('date' if 'date' in d.columns else d.columns[0]); d=d.rename(columns={tc:'time'})
    d['time']=pd.to_datetime(d['time'],utc=True,errors='coerce')
    for c in ['open','high','low','close']: d[c]=pd.to_numeric(d[c],errors='coerce')
    return d.dropna(subset=['time','open','high','low','close']).drop_duplicates('time').sort_values('time').reset_index(drop=True)

def indicators(d):
    d=d.copy()
    for n in [20,50,200]: d[f'ema{n}']=d.close.ewm(span=n,adjust=False).mean()
    d['prior_high20']=d.high.shift(1).rolling(20).max(); d['prior_low20']=d.low.shift(1).rolling(20).min()
    delta=d.close.diff(); gain=delta.clip(lower=0).rolling(14).mean(); loss=(-delta.clip(upper=0)).rolling(14).mean()
    d['rsi']=100-100/(1+gain/loss.replace(0,np.nan))
    tr=pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
    d['atr14']=tr.rolling(14).mean(); return d

def signal(d,i):
    r=d.iloc[i]
    if any(pd.isna(r[k]) for k in ['ema20','ema50','ema200','prior_high20','prior_low20','rsi','atr14']): return 0,0
    buy=35*int(r.ema20>r.ema50>r.ema200)+35*int(r.close>r.prior_high20)+15*int(r.rsi<28)
    sell=35*int(r.ema20<r.ema50<r.ema200)+35*int(r.close<r.prior_low20)+15*int(r.rsi>72)
    if buy>=35 and buy>sell:return 1,buy
    if sell>=35 and sell>buy:return -1,sell
    return 0,max(buy,sell)

def backtest(d,balance,risk,cost,start=220,end=None):
    d=d.reset_index(drop=True); end=min(len(d)-1,end if end is not None else len(d)-1)
    eq=float(balance); peak=eq; maxdd=0.; trades=[]; pos=0; i=max(220,start)
    while i<=end:
        r=d.iloc[i]
        if pos:
            sh=r.low<=stop if pos==1 else r.high>=stop
            th=r.high>=target if pos==1 else r.low<=target
            if sh or th:
                ex=stop if sh else target; raw=((ex-entry)/entry)*pos; net=raw-cost/10000
                frac=abs(stop-entry)/entry; pnl=riskcash*net/max(frac,1e-9); eq+=pnl
                trades.append({'Entry UTC':d.loc[entryidx,'time'],'Exit UTC':r.time,'Side':'BUY' if pos==1 else 'SELL','Entry':entry,'Exit':ex,'PnL $':pnl,'Balance $':eq,'Exit reason':'Stop' if sh else 'Target'})
                pos=0
        if not pos and i<end:
            dire,score=signal(d,i); atr=d.loc[i,'atr14']
            if dire and pd.notna(atr) and atr>0:
                pos=dire; entryidx=i+1; entry=float(d.loc[entryidx,'open']); stop=entry-pos*1.5*float(atr); target=entry+pos*2.25*float(atr); riskcash=max(eq,0)*risk/100
        peak=max(peak,eq); maxdd=max(maxdd,(peak-eq)/peak if peak>0 else 0); i+=1
    t=pd.DataFrame(trades); wins=int((t['PnL $']>0).sum()) if len(t) else 0
    gp=float(t.loc[t['PnL $']>0,'PnL $'].sum()) if len(t) else 0.; gl=float(-t.loc[t['PnL $']<0,'PnL $'].sum()) if len(t) else 0.
    return {'trades':t,'return':(eq/balance-1)*100,'dd':maxdd*100,'win':wins/len(t)*100 if len(t) else np.nan,'pf':gp/gl if gl else (np.inf if gp else np.nan)}

with st.sidebar:
    st.header('Settings'); balance=st.number_input('Virtual starting balance ($)',50.,100000.,500.,50.)
    interval=st.selectbox('Candle interval',['1h','1d']); period=st.selectbox('Historical period',['3mo','6mo','1y','2y'],index=2)
    risk=st.slider('Risk budget per trade (%)',0.1,3.0,0.5,0.1); cost=st.slider('Assumed round-trip costs (bps)',0.,30.,8.,0.5)
if st.button('Refresh public market data'): st.cache_data.clear()
rows=[]; data={}
with st.spinner('Fetching public market data...'):
    for name,(ticker,group) in MARKETS.items():
        try:
            raw=fetch(ticker,period,interval)
            if len(raw)<240: rows.append({'Market':name,'Type':group,'Signal':'DATA UNAVAILABLE','Score / 85':0,'Bars':len(raw)}); continue
            d=indicators(raw); dire,score=signal(d,len(d)-1); r=d.iloc[-1]
            rows.append({'Market':name,'Type':group,'Signal':'BUY candidate' if dire==1 else 'SELL candidate' if dire==-1 else 'NO TRADE','Score / 85':score,'Last price':float(r.close),'RSI':round(float(r.rsi),2) if pd.notna(r.rsi) else np.nan,'Latest candle UTC':str(r.time),'Bars':len(d)})
            data[name]=d
        except Exception: rows.append({'Market':name,'Type':group,'Signal':'DATA ERROR','Score / 85':0,'Bars':0})
st.subheader('1. All-market scanner'); st.dataframe(pd.DataFrame(rows).sort_values(['Score / 85','Market'],ascending=[False,True]),use_container_width=True,hide_index=True)
st.caption('Rule score is not win probability. Public Yahoo Finance prices can differ from broker prices.')
st.subheader('2. Per-market historical test'); reports=[]
for name,d in data.items():
    split=int(len(d)*.70); train=backtest(d,balance,risk,cost,220,max(220,split-1)); test=backtest(d,balance,risk,cost,max(220,split),len(d)-1)
    reports.append({'Market':name,'Holdout trades':len(test['trades']),'Holdout win rate %':test['win'],'Holdout return %':test['return'],'Holdout max drawdown %':test['dd'],'Holdout profit factor':test['pf'],'Train trades':len(train['trades']),'Train win rate %':train['win']})
if reports:
    rep=pd.DataFrame(reports); st.dataframe(rep,use_container_width=True,hide_index=True)
    st.info('Each market is tested with a separate virtual balance. Average market returns are not a real combined portfolio result. The final 30% is the holdout period.')
    c1,c2,c3=st.columns(3); c1.metric('Markets with data',len(rep)); c2.metric('Average holdout return',f"{rep['Holdout return %'].mean():+.2f}%")
    wr=rep['Holdout win rate %'].dropna(); c3.metric('Average holdout win rate',f'{wr.mean():.2f}%' if len(wr) else 'N/A')
else: st.info('No markets currently have enough public data. Try Daily candles or refresh later.')
if data:
    st.subheader('3. Market detail'); selected=st.selectbox('Choose market',list(data)); d=data[selected]; dire,score=signal(d,len(d)-1); r=d.iloc[-1]
    c1,c2,c3=st.columns(3); c1.metric('Last price',f'{r.close:.6f}'); c2.metric('Rule score',f'{score}/85'); c3.metric('Signal','BUY candidate' if dire==1 else 'SELL candidate' if dire==-1 else 'NO TRADE')
    chart=d[['time','close','ema20','ema50','ema200']].melt(id_vars='time',var_name='series',value_name='price'); st.plotly_chart(px.line(chart,x='time',y='price',color='series',title=f'{selected} price and EMA indicators'),use_container_width=True)
    split=int(len(d)*.70); test=backtest(d,balance,risk,cost,max(220,split),len(d)-1); st.write('Holdout closed trades')
    if len(test['trades']): st.dataframe(test['trades'].tail(200),use_container_width=True,hide_index=True)
    else: st.info('No closed trades in holdout period; few or zero trades do not prove reliability.')
st.subheader('Limitations and safe use')
st.markdown('''- Rule-based research tool, not a trained AI model; no Vantage connection or live orders.\n- Public data may be missing or differ from broker prices.\n- Simplified backtest does not model exact spread, swaps, slippage, leverage, margin, contract sizes or partial fills.\n- If stop and target are touched in one candle, stop is assumed first.\n- Results may be noisy with few trades; do not repeatedly tune against holdout data.\n- 97% win rate and 30,000% monthly return are not guaranteed. A high win rate can still lose money if losses are larger than wins.\n- Paper test before considering any live trading.''')
