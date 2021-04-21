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

first_run = True
# while avd == 0:


data = yf.download(tickers=stock, period='5h', interval='1h')
data = data.tz_convert('America/New_York')


print(data)

todays_date = datetime.datetime.now()
index = pd.date_range(todays_date, periods=1, freq='D')

df = pd.DataFrame(index=index) #how to add the candle data here?!
df = df.fillna(1)

stamp = data.index.tolist()
caca = stamp[len(stamp)-1]

print(caca)

removed = data.drop(pd.Timestamp(caca)) #how to get last date from index?S@!#@$%
print(removed)

df = removed.append(df)
print(df)