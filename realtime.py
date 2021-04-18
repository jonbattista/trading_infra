# Webhook requirements
import requests
import json

# Raw package
import pandas as pd

# Data Source
import yfinance as yf
from yahoo_fin.stock_info import *

# Graphing Option
import plotly.graph_objs as go

# Getting Live Market Data Intervals

stock = 'btc-usd'  # input("Enter a Ticker: ")

avd = 0

while avd == 0:

    data = yf.download(tickers=stock, period='5h', interval='1h')

    # Strip the high/low data => create support, resistance


    high = data.High
    # print(high)

    last3H0 = high.tail(3)  # last 3 including active candle [0]
    last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
    # print(last3H1)

    low = data.Low
    # print(low)

    low3H0 = low.tail(3)  # last 3 including active candle [0]
    low3H1 = low.tail(4).head(3)  # last 3 not including active [1]
    # print(low3H1)


    res0 = max(last3H0)  # MAX of prior including active [0]
    res1 = max(last3H1)

    sup0 = min(low3H0)  # Min of prior including active [0]
    sup1 = min(low3H1)

    # live price
    live = get_live_price(stock)

    # AVD - Checks is live value is below or above prior candle
    # support/resistance
    if live > res1:
        avd = 1
    elif live < sup1:
        avd = -1
    else:
        avd = 0


data = yf.download(tickers=stock, period='5h', interval='1h')

# Strip the high/low data => create support, resistance


high = data.High
# print(high)

last3H0 = high.tail(3)  # last 3 including active candle [0]
last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
# print(last3H1)

low = data.Low
# print(low)

low3H0 = low.tail(3)  # last 3 including active candle [0]
low3H1 = low.tail(4).head(3)  # last 3 not including active [1]
# print(low3H1)


res0 = max(last3H0)  # MAX of prior including active [0]
res1 = max(last3H1)

sup0 = min(low3H0)  # Min of prior including active [0]
sup1 = min(low3H1)

# live price
live = get_live_price(stock)

# AVD - Checks is live value is below or above prior candle
# support/resistance
if live > res1:
    avd = 1
elif live < sup1:
    avd = -1
else:
    avd = 0

# AVN  - AVD value of last non-zero condition stored.
if avd!=0:
    avn=avd
    prior_avd = avd
else:
    avn=prior_avd

# TSL line
if avn=1:
    tsl = sup0
else:
    ts = res0

#Buy/sell signal 

close = data.Close.tail(2).head(1) #prior canlde close
Buy = live > tsl and live > clsoe #Crossover of live price over tsl and higher than last candle close
Sell = live < tsl and live < close #Crossunder of live price under tsl and lower than last candle close
print(Buy)
print(Sell)


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
# fig.show()


# Webhook OUT
API_key = 'key here'
API_password = 'pass here'
webhook = 'https://trading.battista.dev/' \
          '?APCA_API_KEY_ID=PKI8VO3NCM8G2NJ0SX0O&APCA_API_SECRET_KEY=LUyqGDO6hlKvezjnaMG4U1o7HJIQCUBZr2xcwaYQ'

outdata = {
    "qty": 5000,
    "ticker": "ticker",
    "price": "close",
    "stop": "low",
    "side": "buy"
}

r = requests.post(webhook, data=json.dumps(outdata))
print(r)
