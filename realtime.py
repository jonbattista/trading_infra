# Webhook requirements
import requests
import json
import time
# Raw package
import pandas as pd
import numpy as np
# Data Source
import yfinance as yf
from yahoo_fin.stock_info import *

# Graphing Option
import plotly.graph_objs as go

from datetime import datetime
from pytz import timezone
import pytz

import dash
import dash_core_components as dcc
import dash_html_components as html

now = datetime.now(timezone('UTC'))

from dash.dependencies import Output, Input

# Getting Live Market Data Intervals

stock = 'btc-usd'  # input("Enter a Ticker: ")
initial_candle = True
avd = -1
count = None
date_list = []
tsl_list = []
new_data = None

def buildCandleDataFrame(live, data):
    #print(f'Live Value is {live}')
    #print(data)
    length = len(data.index) - 2
    #print(f'Old: {data.iloc[length]}')
    #print(f'Close Value is {init_close}')
    #print(data.iloc[-1])

    open_value = round(data['Open'].iloc[-1], 2)
    high_value = round(data['High'].iloc[-1], 2)
    low_value = round(data['Low'].iloc[-1], 2)
    close_value = round(data['Close'].iloc[-1], 2)
    close_value = round(data['Close'].iloc[-1], 2)

    # Set the high value if it is greater than the open
    if live > high_value:
        print(f'Updating High Value from {high_value} to {live}')
        high_value = live

    # Set the low value if it is less than the open
    if live < low_value:
        print(f'Updating Low Value from {low_value} to {live}')
        low_value = live

    # After we have receieved any value, set close to current value
    if live != close_value:
        print(f'Updating Close Value from {close_value} to {live}')
        close_value = live

    todays_date = datetime.now()
    index = pd.date_range(todays_date, periods=1, freq='D')

    input = {'Open':open_value, 'High':high_value,'Low':low_value,'Volume':0,'Close':close_value}

    new_candle = pd.DataFrame(input, index=index)

    stamp = data.index.tolist()
    index_stamp = stamp[len(stamp)-1]

    removed = data.drop(pd.Timestamp(index_stamp))
    #print(removed)

    new_data = removed.append(new_candle)
    print(new_data)
    #data.iloc[-1]=[open_value,high_value,low_value,close_value,0,0]


    #print(data)
#    todays_date = datetime.datetime.now()
#    index = pd.date_range(todays_date, periods=1, freq='D')#

#    input = {'Open':open,'High':high,'Low':low,'Volume':0,'Close':close}
#    
#    new_candle = pd.DataFrame(input, index=index)#

#    stamp = data.index.tolist()
#    index_stamp = stamp[len(stamp)-1]#

#    removed = data.drop(pd.Timestamp(index_stamp))
#    print(removed)#

#    new_data = removed.append(new_candle)
#    print(new_data)
    #print(f'New: {data.iloc[length]}')
    return new_data

app = dash.Dash(__name__)
  
app.layout = html.Div(
    [
        dcc.Graph(id = 'candles', animate = True),
        dcc.Interval(
            id = 'update-candles',
            interval = 1000,
            n_intervals = 0
            ),
    ]
)
  
@app.callback(
    Output('candles', 'figure'),
    [Input('update-candles', 'n_intervals')]
)
def update_candles(n):
    global count
    global initial_data
    global initial_candle
    global new_data
    old_data = None
    fig = go.Figure()
    #print(locals())
    #print(f'Count is {count}')
    #print(f'New Data is {initial_data}')
    if count == 59 or count == None:
        print('Fetching new data!')
        initial_data = yf.download(tickers=stock, period='5h', interval='1h', progress=False)
        initial_data = initial_data.tz_convert('America/New_York')
        count = 0
    length = len(initial_data.index) - 1
    #print(f'New data is {new_data}')
    #print(initial_data.iloc[-1])
    starttime = time.time()
    
        
    live = round(float(get_live_price(stock)), 2)
    print(f'Last Data is {live}')

    if initial_candle:
        new_data = buildCandleDataFrame(live, initial_data)
        initial_candle = False
    else:
         new_data = buildCandleDataFrame(live, new_data)
    #length = len(data.index) -1
    
    #print(f'Latest Data: {data.iloc[length]}')
    #print(data)
    # Strip the high/low data => create support, resistance


    high = new_data.High
    #print(high)

    last3H0 = high.tail(3)  # last 3 including active candle [0]
    last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
    # print(last3H1)

    low = new_data.Low
    # print(low)

    low3H0 = low.tail(3)  # last 3 including active candle [0]
    low3H1 = low.tail(4).head(3)  # last 3 not including active [1]
    # print(low3H1)


    res0 = float(max(last3H0))  # MAX of prior including active [0]
    res1 = float(max(last3H1))

    sup0 = float(min(low3H0))  # Min of prior including active [0]
    sup1 = float(min(low3H1))
    # print(f'Resistance 0 is {res0}')
    # print(f'Resistance 1 is {res1}')
    # print(f'Support 0 is {sup0}')
    # print(f'Support 1 is {sup1}')

    # live price
    #print(f'Live Candle is:')
    #print(live_candle)
    #sec = time.localtime().tm_sec
    #print(f'Current Second is {sec}')

#    if sec == 59 or sec == 0:
#        old_data = data
#        data['open'].iloc[0] = np.nan
#        data['high'].iloc[0] = np.nan
#        data['low'].iloc[0] = np.nan
#        data['close'].iloc[0] = np.nan
#        print(candle_df)

    # AVD - Checks is live value is below or above prior candle
    # support/resistance
    if live > res1:
        avd = 1
    elif live < sup1:
        avd = -1
    else:
        avd = 0

    # AVN  - AVD value of last non-zero condition stored.
    if avd != 0:
        avn = avd
        #prior_avd = avd
    else:
        #avn=prior_avd
        avn = 0

    # TSL line
    if avn == 1:
        tsl = sup0
    else:
        tsl = res0

    # print(f'AVD is {avd}')
    # print(f'AVN is {avn}')
    # print(f'TSL is {tsl}')
    # print(f'Last Price is {live}')
    #Buy/sell signal 

    close_value = new_data.Close.tail(1).iloc[0]#prior canlde close
    close = float(close_value)
    #print(f'Close is {close}')

    if live > tsl and live > close:
        Buy = True  #Crossover of live price over tsl and higher than last candle close
    else:
        Buy = False

    if live < tsl and live < close:
        Sell = True #Crossunder of live price under tsl and lower than last candle close
    else:
        Sell = False


    #print(Buy)
    #print(Sell)

#    if old_data is not None and old_data['Open'] != data['Open']:
#        print(old_data.Open.tail(1).iloc[0])
#        print(data.Open.tail(1).iloc[0])
#        # Candle stick
#        fig.add_trace(
#            go.Candlestick(x=data.index,
#                           open=data['Open'],
#                           high=data['High'],
#                           low=data['Low'],
#                           close=data['Close'], name='Market Data'))
#    else:
#        raise dash.exceptions.PreventUpdate()
    candlesticks = update_candlesticks(new_data)
    print(candlesticks)
    fig.add_trace(candlesticks)
    #print(date_list)
#print(tsl_list)

# Add TSL line
#    fig.add_trace(
#        update_tsl(tsl, tsl_list, date_list)
#    )

#    if Buy:
#        fig.add_vline(x=now_est)#

#    if Sell:
#        fig.add_vline(x=now_est)

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
            dict(count=15, label="15m", step="minute", stepmode="backward"),
            dict(count=30, label="30m", step="minute", stepmode="backward"),
            dict(count=1, label="1h", step="hour", stepmode="backward"),
            dict(count=2, label="2h", step="hour", stepmode="backward"),
            dict(step="all")
        ))})
    count += 1
    return fig

def update_candlesticks(data):
    #print(f'Current Data Close is {data.Close.tail(1).iloc[0]}')
    
#    if not old_data is not None:
#        #print(f'Old Data is {old_data}')
#        #print(old_data['Open'].tail(1).iloc[0])
#        #print(data['Open'].tail(1).iloc[0])
#        if old_data != data.Close.tail(1).iloc[0]:#

#            candlesticks = go.Candlestick(x=data.index,
#                               open=data['Open'],
#                               high=data['High'],
#                               low=data['Low'],
#                               close=data['Close'], name='Market Data')
#            old_data = data.Close.tail(1).iloc[0]
#            return candlesticks
#        else:
#            raise dash.exceptions.PreventUpdate()
#    else:
#        candlesticks = go.Candlestick(x=data.index,
#                               open=data['Open'],
#                               high=data['High'],
#                               low=data['Low'],
#                               close=data['Close'], name='Market Data')
    print(data)
    candlesticks = go.Candlestick(x=data.index,
                               open=data['Open'],
                               high=data['High'],
                               low=data['Low'],
                               close=data['Close'], name='Market Data')
    return candlesticks

def update_tsl(tsl, tsl_list, date_list):
    now_utc = pytz.utc.localize(datetime.utcnow())
    now_est = now_utc.astimezone(pytz.timezone("America/New_York"))
    now_est = now_est.strftime('%Y-%m-%d %H:%M:%S%z')
    #print(now_est)
    date_list.append(now_est)
    tsl_list.append(tsl)
    tsl = go.Scatter(
            x=date_list,
            y=tsl_list,
            mode='lines'
        )
    #print(tsl)
    return tsl

if __name__ == '__main__':
    app.run_server(debug=True, port=8080, use_reloader=True)
