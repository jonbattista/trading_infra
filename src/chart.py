import requests
import json
import time
from twelvedata import TDClient
import asyncio
import websocket
import ssl
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from datetime import datetime
from pytz import timezone
import pytz
import dash
import dash_core_components as dcc
import dash_html_components as html
import config
from apscheduler.schedulers.blocking import BlockingScheduler
from dash.dependencies import Output, Input

now = datetime.now(timezone('UTC'))

stock = 'TQQQ'  # input("Enter a Ticker: ")
initial_candle = True
avd = -1
count = None
date_list = []
tsl_list = []
new_data = None
first_run = True
prior_avd = None

def calcTsl(tsl_ts, live):
    global prior_avd
    now_utc = pytz.utc.localize(datetime.utcnow())
    now_est = now_utc.astimezone(pytz.timezone("America/New_York"))
    now_est = now_est.strftime('%Y-%m-%d %H:%M:%S.%f')#
    high = tsl_ts.high
    #print(high)#
    last3H0 = high.tail(3)  # last 3 including active candle [0]
    last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
    # print(last3H1)#
    low = tsl_ts.low
    # print(low)#
    low3H0 = low.tail(3)  # last 3 including active candle [0]
    low3H1 = low.tail(4).head(3)  # last 3 not including active [1]
    # print(low3H1)##
    res0 = float(max(last3H0))  # MAX of prior including active [0]
    res1 = float(max(last3H1))#
    sup0 = float(min(low3H0))  # Min of prior including active [0]
    sup1 = float(min(low3H1))

    if prior_avd is None:
        prior_avd = -1

    print(f'Resistance 0 is {res0}')
    print(f'Resistance 1 is {res1}')
    print(f'Support 0 is {sup0}')
    print(f'Support 1 is {sup1}')
    # AVD - Checks is live value is below or above prior candle
    # support/resistance
    if live > res1:
        avd = 1
    elif live < sup1:
        avd = -1
    else:
        avd = 0#
    # AVN  - AVD value of last non-zero condition stored.
    if avd != 0:
        avn = avd
        prior_avd = avd
    else:
        avn = prior_avd
        #avn = 0
    # TSL line
    if avn == 1:
        tsl = sup0
    else:
        tsl = res0#
    print(f'AVD is {avd}')
    print(f'AVN is {avn}')
    print(f'TSL is {tsl}')
    print(f'Last Price is {live}') #
    close_value = new_data.close.tail(1).iloc[0]
    close = float(close_value)#
    if live > tsl and live > close:
        Buy = True  #Crossover of live price over tsl and higher than last candle close
        print(f'Crossover Buy is True')
    else:
        Buy = False
        print(f'Crossover Buy is False')
    if live < tsl and live < close:
        Sell = True #Crossunder of live price under tsl and lower than last candle close
        print(f'Crossover Sell is True')
    else:
        Sell = False
        print(f'Crossover Sell is False')

def fetchLastCandles(td):
    global first_run
    global df

    ts = td.time_series(
        symbol=stock,
        outputsize=5,
        interval="1min",
        timezone="America/New_York",
        order='asc'
    )
    df = ts.as_pandas()

    if first_run == True:
        first_run = False
        sched = BlockingScheduler()
        sched.add_job(fetchLastCandles, 'interval', args=[td],  minute='0-59', second='25')
        sched.start()

def buildCandleDataFrame(live, data):
    open_value = round(data['open'].iloc[-1], 2)
    high_value = round(data['high'].iloc[-1], 2)
    low_value = round(data['low'].iloc[-1], 2)
    close_value = round(data['close'].iloc[-1], 2)

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

    input = {'open':open_value, 'high':high_value,'low':low_value,'volume':0,'close':close_value}

    new_candle = pd.DataFrame(input, index=index)

    stamp = data.index.tolist()
    index_stamp = stamp[len(stamp)-1]

    removed = data.drop(pd.Timestamp(index_stamp))

    new_data = removed.append(new_candle)
    print(new_data)
    return new_data

app = dash.Dash(__name__)
  
app.layout = html.Div(children=[

    dcc.Graph(id = 'candles', animate = True),
    dcc.Interval(
        id = 'update-candles',
        interval = 5*1000,
        n_intervals = 0
        ),
#    dcc.Graph(id = 'tsl', animate = True),
#    dcc.Interval(
#        id = 'update-tsl',
#        interval = 5*1000,
#        n_intervals = 0
#        ),
])
  
@app.callback(
    Output('candles', 'figure'),
    [Input('update-candles', 'n_intervals')]
)
def update_candles(n):
    global count
    global df
    global initial_candle
    global new_data
    global stock
    global td
    global first_run

    old_data = None

    fig = go.Figure()

    if first_run == True:
        print('first run')
        fetchLastCandles(td)

    price = requests.get(f"https://api.twelvedata.com/price?symbol={stock}&apikey={config.API_KEY}").json()
    live = round(float(price['price']), 2)
    print(f'Last Live Price is {live}')

    if initial_candle:
        new_data = buildCandleDataFrame(live, df)
        initial_candle = False
        count = 0
    else:
         new_data = buildCandleDataFrame(live, new_data)

    calcTsl(new_data, live)
    candlesticks = update_candlesticks(new_data)
    fig.add_trace(candlesticks)

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
    candlesticks = go.Candlestick(x=data.index,
                               open=data['open'],
                               high=data['high'],
                               low=data['low'],
                               close=data['close'], name='Market Data')
    #print(candlesticks)
    return candlesticks

#@app.callback(
#    Output('tsl', 'figure'),
#    [Input('update-tsl', 'n_intervals')]
#)
#def update_tsl(n):
#    global tsl_ts
#    fetchLastCandles(tsl_ts)
#    fig = go.Figure()
#    now_utc = pytz.utc.localize(datetime.utcnow())
#    now_est = now_utc.astimezone(pytz.timezone("America/New_York"))
#    now_est = now_est.strftime('%Y-%m-%d %H:%M:%S.%f')#
#    high = tsl_ts.high
#    #print(high)#
#    last3H0 = high.tail(3)  # last 3 including active candle [0]
#    last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
#    # print(last3H1)#
#    low = tsl_ts.low
#    # print(low)#
#    low3H0 = low.tail(3)  # last 3 including active candle [0]
#    low3H1 = low.tail(4).head(3)  # last 3 not including active [1]
#    # print(low3H1)##
#    res0 = float(max(last3H0))  # MAX of prior including active [0]
#    res1 = float(max(last3H1))#
#    sup0 = float(min(low3H0))  # Min of prior including active [0]
#    sup1 = float(min(low3H1))
#    # print(f'Resistance 0 is {res0}')
#    # print(f'Resistance 1 is {res1}')
#    # print(f'Support 0 is {sup0}')
#    # print(f'Support 1 is {sup1}')#
#    # AVD - Checks is live value is below or above prior candle
#    # support/resistance
#    if live > res1:
#        avd = 1
#    elif live < sup1:
#        avd = -1
#    else:
#        avd = 0#
#    # AVN  - AVD value of last non-zero condition stored.
#    if avd != 0:
#        avn = avd
#        #prior_avd = avd
#    else:
#        #avn=prior_avd
#        avn = 0#
#    # TSL line
#    if avn == 1:
#        tsl = sup0
#    else:
#        tsl = res0#
#    # print(f'AVD is {avd}')
#    # print(f'AVN is {avn}')
#    # print(f'TSL is {tsl}')
#    # print(f'Last Price is {live}') #
#    close_value = new_data.close.tail(1).iloc[0]
#    close = float(close_value)#
#    if live > tsl and live > close:
#        Buy = True  #Crossover of live price over tsl and higher than last candle close
#    else:
#        Buy = False#
#    if live < tsl and live < close:
#        Sell = True #Crossunder of live price under tsl and lower than last candle close
#    else:
#        Sell = False
#    #print(now_est)
#    date_list.append(now_est)
#    tsl_list.append(tsl)
#    tsl = go.Scatter(
#            x=date_list,
#            y=tsl_list,
#            mode='lines'
#        )
#    print(f'TSL is {tsl}')
#    fig.add_trace(tsl, tsl_list, date_list)#
#        # Add Titles
#    fig.update_layout(
#        title='TSL Crossover',
#        yaxis_title='TSL'
#    )#
#    # Axis and control
#    fig.update_xaxes(
#        rangeslider_visible=True,
#        rangeselector={'buttons': list((
#            dict(count=15, label="15m", step="minute", stepmode="backward"),
#            dict(count=30, label="30m", step="minute", stepmode="backward"),
#            dict(count=1, label="1h", step="hour", stepmode="backward"),
#            dict(count=2, label="2h", step="hour", stepmode="backward"),
#            dict(step="all")
#    ))})
#    return fig

if __name__ == '__main__':
    global td
    td = TDClient(apikey=config.API_KEY)
    app.run_server(debug=True, port=8080, use_reloader=True)