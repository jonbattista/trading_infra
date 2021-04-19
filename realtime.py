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

avd = -1

date_list = []
tsl_list = []

candle_df = pd.DataFrame(columns = ['open',
                        'high',
                        'low',
                        'close'],
                        index = ['0'])

def buildCandleDataFrame(value, candle_df):
    # Set first received value to open
    print(f'Value is {value}')
    #print(candle_df)
    #candle_df.loc['open'] = value
    if pd.isnull(candle_df['open'].iloc[0]):
        candle_df['open'].iloc[0] = value

    # Set the high value if it is greater than the open
    if value > candle_df['open'].iloc[0] and pd.isnull(candle_df['high'].iloc[0]):
        candle_df['high'].iloc[0] = value

    # Set the low value if it is less than the open
    if value < candle_df['open'].iloc[0] and pd.isnull(candle_df['low'].iloc[0]):
        candle_df['low'].iloc[0] = value

    # Update the high and low values 
    if value > candle_df['high'].iloc[0]:
        candle_df['high'].iloc[0] = value
    elif value < candle_df['low'].iloc[0]:
        candle_df['low'].iloc[0] = value

    # After we have receieved any value, set close to current value
    if not pd.isnull(candle_df['open'].iloc[0]):
        candle_df['close'].iloc[0] = value

    return candle_df

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
    old_data = pd.DataFrame()
    fig = go.Figure()
    data = yf.download(tickers=stock, period='30m', interval='1m', progress=False)
    data = data.tz_convert('America/New_York')


    # Strip the high/low data => create support, resistance


    high = data.High
    #print(high)

    last3H0 = high.tail(3)  # last 3 including active candle [0]
    last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
    # print(last3H1)

    low = data.Low
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
    live = float(get_live_price(stock))
    
    live_candle = buildCandleDataFrame(live, candle_df)
    print(f'Live Candle is:')
    print(live_candle)
    sec = time.localtime().tm_sec
    print(f'Current Second is {sec}')

    if sec == 59 or sec == 0:
        old_data = data
        candle_df['open'].iloc[0] = np.nan
        candle_df['high'].iloc[0] = np.nan
        candle_df['low'].iloc[0] = np.nan
        candle_df['close'].iloc[0] = np.nan
        print(candle_df)

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

    close_value = data.Close.tail(1).iloc[0]#prior canlde close
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
    candlesticks = update_candlesticks(data, old_data)
    print(f'Candlesticks is {candlesticks}')
    fig.add_trace(candlesticks)
    #print(date_list)
    #print(tsl_list)

    # Add TSL line
    fig.add_trace(
        update_tsl(tsl, tsl_list, date_list)
    )

    if Buy:
        fig.add_vline(x=now_est)

    if Sell:
        fig.add_vline(x=now_est)

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

    return fig

def update_candlesticks(data, old_data):
    print(f'Current Data Close is {data.Close.tail(1).iloc[0]}')
    
    if not old_data.empty:
        print(f'Old Data is {old_data.Close.tail(1).iloc[0]}')
        #print(old_data['Open'].tail(1).iloc[0])
        #print(data['Open'].tail(1).iloc[0])
        if old_data.Close.tail(1).iloc[0] != data.Close.tail(1).iloc[0]:

            candlesticks = go.Candlestick(x=data.index,
                               open=data['Open'],
                               high=data['High'],
                               low=data['Low'],
                               close=data['Close'], name='Market Data')
            return candlesticks
        elif old_data.Close.tail(1).iloc[0] == data.Close.tail(1).iloc[0]:
            candlesticks = go.Candlestick(x=data.index,
                               open=data['Open'],
                               high=data['High'],
                               low=data['Low'],
                               close=data['Close'], name='Market Data')
            return candlesticks
    else:
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

    return tsl

if __name__ == '__main__':
    app.run_server(debug=True, port=8080, use_reloader=True)
