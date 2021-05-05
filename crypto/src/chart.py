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
import ssl
from threading import Thread
import websockets

now = datetime.now(timezone('UTC'))

ticker = 'TQQQ'
initial_candle = True
avd = -1
count = None
date_list = []
tsl_list = []
new_data = None
first_run = True
avn = None
live_price = None
data = None
last_minute = None

def on_message(ws, message):
    global live_price
    res = json.loads(message)
    print(f'WS Message is {message}')
    if 'price' in res:
        live_price = res['price']
        print(f'Latest Price is {live_price}')
        buildCandleDataFrame(live_price)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("Connection closed")

def on_open(ws):
    global ticker

    print('New connection established')

    ws.send(json.dumps({
      "action": "subscribe", 
      "params": {
        "symbols": f'{ticker}'
      }
    }))
    app.run_server(debug=True, port=8080, use_reloader=True)
    
def calcTsl(tsl_ts, live):
    global avn

    now_utc = pytz.utc.localize(datetime.utcnow())
    now_est = now_utc.astimezone(pytz.timezone("America/New_York"))
    now_est = now_est.strftime('%Y-%m-%d %H:%M:%S.%f')#
    high = tsl_ts.high
    #print(tsl_ts)
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
        avd = 0

    # AVN  - AVD value of last non-zero condition stored.
    if avd != 0:
        avn = avd

    # TSL line
    if avn == 1:
        tsl = sup0
    else:
        tsl = res0

    print(f'AVD is {avd}')
    print(f'AVN is {avn}')
    print(f'TSL is {tsl}')
    #print(f'Last Price is {live}')

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
    global data

    if first_run == True:
        first_run = False
        sched = BlockingScheduler()
        print('Adding fetchLastCandles job!')
        sched.add_job(fetchLastCandles, 'cron', args=[td], minute='0-59', second='25')
        sched.start()

    #print('Fetching Latest Candles!')
    ts = td.time_series(
        symbol=ticker,
        outputsize=4,
        interval="1min",
        timezone="America/New_York",
        order='asc',
        prepost=True
    )
    data = ts.as_pandas()

    #print(data)

def buildCandleDataFrame(live):
    global td
    global data
    global new_data
    global current_minute
    global last_minute

    if data is None:
        fetchLastCandles(td)
        time.sleep(3)

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
    date = datetime.now()
    current_minute = date.strftime('%Y-%m-%d %H:%M:00.000000')
    #print(f'Last Minute was {current_minute}')
    print(f'Current Minute is {current_minute}')

#    if current_minute != last_minute and last_minute is not None:
#        new_candle.index.values[0] = pd.Timestamp(current_minute)
#        new_candle.index.values[1] = pd.Timestamp(last_minute)
#    else:
#        last_minute = current_minute
#        new_candle.index.values[0] = pd.Timestamp(current_minute)
    new_candle.index.values[0] = pd.Timestamp(current_minute)
    print(f'New Candle is {new_candle}')
    index_len = len(data.index.tolist())

    if index_len > 4 :
        stamp = data.index.tolist()
        index_stamp = stamp[len(stamp)-1]

        removed = data.drop(pd.Timestamp(index_stamp))
        new_data = removed.append(new_candle)
    else:
        new_data = data.append(new_candle)

app = dash.Dash(__name__)
app.layout = html.Div(children=[

    dcc.Graph(id = 'candles', animate = True),
    dcc.Graph(id = 'tsl', animate = True, figure={}),
    dcc.Interval(
        id = 'interval-component',
        interval = 5*1000,
        n_intervals = 0
        ),
])
  
@app.callback(
    Output('candles', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_candles(n):
    global count
    global data
    global initial_candle
    global new_data
    global ticker
    global td
    global first_run
    global live_price
    global ws

    fig = go.Figure()

    if first_run == True:
        print('First run!')
        fetchLastCandles(td)

    if live_price == None:
        price = requests.get(f"https://api.twelvedata.com/price?symbol={ticker}&apikey={config.API_KEY}").json()
        live_price = round(float(price['price']), 2)
    #f"https://api.twelvedata.com/time_series?symbol={ticker}&exchange=Binance&interval=1min&apikey={config.API_KEY}"

    #live = round(float(price['price']), 2)
    #print(f'Last Data is {live}')

    if initial_candle:
        buildCandleDataFrame(live_price)
        initial_candle = False
        count = 0
    #else:
    #     new_data = buildCandleDataFrame()
    if new_data is not None:
        buildCandleDataFrame(live_price)
        print(f'New Data is {new_data}')
        calcTsl(new_data, live_price)
        candlesticks = go.Candlestick(x=new_data.index,
                               open=new_data['open'],
                               high=new_data['high'],
                               low=new_data['low'],
                               close=new_data['close'], name='Market Data')
        fig.add_trace(candlesticks)

        # Add Titles
        fig.update_layout(
            title=ticker + 'Live Price Data',
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
        #print(f'Candlestick Fig is {fig}')
        return fig
    else:
        return {}

@app.callback(
    Output('tsl', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_tsl(n):
    global new_data
    global live_price
    global tsl_list

    fig = go.Figure()
    print(f'TSL New Data is {new_data}')
    if new_data is not None:
        now_utc = pytz.utc.localize(datetime.utcnow())
        now_est = now_utc.astimezone(pytz.timezone("America/New_York"))
        now_est = now_est.strftime('%Y-%m-%d %H:%M:%S.%f')#
        high = new_data.high
        #print(high)#
        last3H0 = high.tail(3)  # last 3 including active candle [0]
        last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
        # print(last3H1)#
        low = new_data.low
        # print(low)#
        low3H0 = low.tail(3)  # last 3 including active candle [0]
        low3H1 = low.tail(4).head(3)  # last 3 not including active [1]
        # print(low3H1)##
        res0 = float(max(last3H0))  # MAX of prior including active [0]
        res1 = float(max(last3H1))#
        sup0 = float(min(low3H0))  # Min of prior including active [0]
        sup1 = float(min(low3H1))
        # print(f'Resistance 0 is {res0}')
        # print(f'Resistance 1 is {res1}')
        # print(f'Support 0 is {sup0}')
        # print(f'Support 1 is {sup1}')#
        # AVD - Checks is live value is below or above prior candle
        # support/resistance
        if live_price > res1:
            avd = 1
        elif live_price < sup1:
            avd = -1
        else:
            avd = 0#
        # AVN  - AVD value of last non-zero condition stored.
        if avd != 0:
            avn = avd
            #prior_avd = avd
        else:
            #avn=prior_avd
            avn = 0#
        # TSL line
        if avn == 1:
            tsl = sup0
        else:
            tsl = res0#
        # print(f'AVD is {avd}')
        # print(f'AVN is {avn}')
        # print(f'TSL is {tsl}')
        # print(f'Last Price is {live_price}') #
        close_value = new_data.close.tail(1).iloc[0]
        close = float(close_value)#
        if live_price > tsl and live_price > close:
            Buy = True  #Crossover of live price over tsl and higher than last candle close
        else:
            Buy = False#
        if live_price < tsl and live_price < close:
            Sell = True #Crossunder of live price under tsl and lower than last candle close
        else:
            Sell = False

        #print(now_est)
        date_list.append(now_est)
        tsl_list.append(tsl)
        tsl = go.Scatter(
                x=date_list,
                y=tsl_list,
                mode='lines'
            )
        #print(f'TSL is {tsl}')
        fig.add_trace(tsl)
            # Add Titles
        fig.update_layout(
            title='TSL Crossover',
            yaxis_title='TSL'
        )#
        # Axis and control
        fig.update_xaxes(
            rangeslider_visible=True,
            rangeselector={'buttons': list((
                dict(count=15, label="15m", step="minute", stepmode="backward"),
                dict(count=30, label="30m", step="minute", stepmode="backward"),
                dict(count=1, label="1h", step="hour", stepmode="backward"),
                dict(count=2, label="2h", step="hour", stepmode="backward"),
                dict(step="all")
        ))})
        #print(f'TSL Fig is {fig}')
        return fig
    else:
        return {}

def run_webserver():
    print('Spawing Webserver...')
    app.run_server(debug=True, port=8080, use_reloader=True)

def run_ws():
    global live_price
    with websockets.connect(f"wss://ws.twelvedata.com/v1/quotes/price?apikey={config.API_KEY}") as websocket:
        subscribe = json.dumps({
          "action": "subscribe", 
          "params": {
            "symbols": f'{ticker}'
          }
        })
        print(subscribe)
        websocket.send(subscribe)

        res = json.loads(websocket.recv())
        print(f'WS Message is {message}')
        if 'price' in res:
            live_price = res['price']
            print(f'Latest Price is {live_price}')
            buildCandleDataFrame(live_price)

if __name__ == '__main__':
    global td
    global ws
    td = TDClient(apikey=config.API_KEY)
    #websocket.enableTrace(True)
#    ws = websocket.WebSocketApp(f"wss://ws.twelvedata.com/v1/quotes/price?apikey={config.API_KEY}",
#                          on_open = on_open,
#                          on_message = on_message,
#                          on_error = on_error,
#                          on_close = on_close)
#    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    ws_task = Thread(target=run_ws)
    webserver_task = Thread(target=run_webserver)
    ws_task.start()
    #webserver_task.start()

