#Time
from datetime import datetime
from pytz import timezone

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

data = yf.download(tickers=stock, period='5h', interval='1h')
data = data.tz_convert('America/New_York')

print(data)

todays_date = datetime.datetime.now()
index = pd.date_range(todays_date, periods=1, freq='D')

input = {'Open':1, 'High':3,'Low':1,'Volume':15,'Close':1}
new_candle = pd.DataFrame(input, index=index)

stamp = data.index.tolist()
index_stamp = stamp[len(stamp)-1]

removed = data.drop(pd.Timestamp(index_stamp))
print(removed)

new_data = removed.append(new_candle)
print(new_data)