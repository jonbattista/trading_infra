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

item = data.High.tail(1)
item2 = data.High.tail(0)

data = data.copy()
data1  = data.transpose()

#print(data1)
caca = data1.to_numpy().flatten()
caca[6]=100
#print(caca)

new  = pd.DataFrame()
print(data)

todays_date = datetime.datetime.now()
print(todays_date)
index = pd.date_range(todays_date, periods=1, freq='D')


df = pd.DataFrame(index=index) #how to add the candle data here?!
df = df.fillna(1)

stamp = type(data.index)
print(stamp)
removed = data.drop(pd.Timestamp('2021-04-20 22:00:00-4:00')) #how to get last date from index?S@!#@$%
print(removed)

df = removed.append(df)
print(df)