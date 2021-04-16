# Raw package
import pandas as pd

# Data Source
import yfinance as yf
from yahoo_fin.stock_info import *

# Graphing Option
import plotly.graph_objs as go

# Getting Live Market Data Intervals

stock = input("Enter a Ticker: ")

data = yf.download(tickers=stock, period='1d', interval='1m')
print(data)
last=data.tail(3)
print(last)

#res = [sub[1] for sub in data]
#print(res)

fig = go.Figure()

# Candle stick
fig.add_trace(
    go.Candlestick(x=data.index,
                   open=data['Open'],
                   high=data['High'],
                   low=data['Low'],
                   close=data['Close'], name='Market Data'))
# Add Titles
fig.update_layout(
    title=stock + 'Live Price Data',
    yaxis_title='Price (USD/share)'
)

#Axis and control
fig.update_xaxes(
    rangeslider_visible=True,
    rangeselector={'buttons': list((
        dict(count=15, label="15min", step="minute", stepmode="backward"),
        dict(count=45, label="45min", step="minute", stepmode="backward"),
        dict(count=1, label="1h", step="hour", stepmode="backward"),
        dict(count=2, label="2h", step="hour", stepmode="backward"),
        dict(step="all")
    ))})
fig.show()
#print(get_live_price(stock))
