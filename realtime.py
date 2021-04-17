# Raw package
import pandas as pd

# Data Source
import yfinance as yf
from yahoo_fin.stock_info import *

# Graphing Option
import plotly.graph_objs as go

# Getting Live Market Data Intervals

stock = input("Enter a Ticker: ")

data = yf.download(tickers=stock, period='2d', interval='1h')

# Strip the high/low data => create suport, resistance
high = data.High
last4H = high.tail(4)  # last 4 closes
resistance1 = max(last4H.head(3))  # MAX of prior loop prior closes max
print(high)
print('resistance-1')
print(resistance1)

resistance = max(high.tail(3))  # last 3 closes max
print('resistance')
print(resistance)

low = data.Low
print(low)
last3L = low.tail(4)  # last 4 closes
support1 = min(last3L.head(3))  # Min of prior lop
print('support-1')
print(support1)
support = min(low.tail(3))  # last 3 closes min
print('support')
print(support)

# live price
live = get_live_price(stock)
print(live)

# AVD - Checks is live value is below or below prior candle
# support/resistance
if live > resistance1:
    AVD = 1
elif live < support1:
    AVD = -1
else:
    AVD = 0
print(AVD)

# AVN  - AVD value of last non-zero condition stored.
def valuewhen(condition, source, occurrence):
    return source \
        .reindex(condition[condition].index) \
        .shift(-occurrence) \
        .reindex(source.index) \
        .ffill()  # error in this functions!!#$%@#!~#@!@


AVN = valuewhen(AVD != 0, AVD, 0)

# TSL line....TDB

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

# Axis and control
fig.update_xaxes(
    rangeslider_visible=True,
    rangeselector={'buttons': list((
        #  dict(count=15, label="15min", step="minute", stepmode="backward"),
        # dict(count=45, label="45min", step="minute", stepmode="backward"),
        dict(count=1, label="1h", step="hour", stepmode="backward"),
        dict(count=2, label="2h", step="hour", stepmode="backward"),
        dict(step="all")
    ))})
fig.show()
