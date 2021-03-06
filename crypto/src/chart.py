import requests
import json
import time
import asyncio
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
from dash.dependencies import Output, Input
from sqlalchemy import create_engine
import pymysql.cursors
import logging
from sys import stdout
import mysql.connector as sql

import pandas as pd

now = datetime.now(timezone('UTC'))

ticker = 'BTC/USD'
initial_candle = True
avd = -1
count = None
date_list = []
tsl_list = []
avn_list = []
new_data = None
first_run = True
avn = None
live_price = None
data = None
last_minute = None
database = "trades"
old_fig = {}
tsl_array=[]

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)

def checkTables(table,cursor):
    stmt = "SHOW TABLES LIKE '%s' "% ('%'+str(table)+'%')
    cursor.execute(stmt)
    result = cursor.fetchone()          
    return result

def calcTsl(data):
    live = data["close"].iloc[-1]

    print(f"Last Price is {live}")
    global avn

    print(data)
    now_utc = pytz.utc.localize(datetime.utcnow())
    now_est = now_utc.astimezone(pytz.timezone("America/New_York"))
    now_est = now_est.strftime('%Y-%m-%d %H:%M:%S.%f')#
    high = data.high
    #print(tsl_ts)
    #print(high)#
    last3H0 = high.tail(3)  # last 3 including active candle [0]
    last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
    # print(last3H1)#
    low = data.low
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
    tsl_array.append(tsl)
    print(tsl_array)
    #print(f'Last Price is {live}')

    close_value = data.close.tail(1).iloc[0]
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

def fetchLastCandles(dbConnection):
    try:
        data = pd.read_sql_query(f"select * from `{ticker}`", dbConnection);
    except Exception as e:
        print(e)
    
    pd.set_option('display.expand_frame_repr', False)
    print(f"Fetched Table: {data}")
    return data

app = dash.Dash(__name__,suppress_callback_exceptions=True)

def serve_layout():
    return html.Div(children=[

    dcc.Graph(id = 'candles'),
    html.Div([
        html.Div([
            dcc.Graph(id = 'tsl'),
        ], className='six columns'),
        html.Div([
            dcc.Graph(id = 'avn'),
        ], className='six columns')
    ], className='row'),
    dcc.Interval(
        id = 'interval-component',
        interval = 10*1000,
        n_intervals = 0
        ),
    ])

app.layout = serve_layout
  
@app.callback(
    Output('candles', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_candles(n):
    global ticker
    global old_fig
    global database
    global new_data

    try:
        sqlEngine = create_engine(f'mysql+pymysql://root:{config.DB_PASS}@127.0.0.1/{database}', pool_recycle=3600)
    except Exception as e:
        print(e)

    connection = sqlEngine.raw_connection()
    cursor = connection.cursor()
    dbConnection = sqlEngine.connect()

    fig = go.Figure()

    new_data = fetchLastCandles(dbConnection)
    dbConnection.close()
    
    if new_data is not None:
        calcTsl(new_data)

        candlesticks = go.Candlestick(x=new_data['datetime'],
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
                dict(count=15, label="15m", step="minute", stepmode="backward"),
                dict(count=30, label="30m", step="minute", stepmode="backward"),
                dict(count=1, label="1h", step="hour", stepmode="backward"),
                dict(count=2, label="2h", step="hour", stepmode="backward"),
                dict(step="all")
            ))})
        old_fig = fig

        return fig
    else:
        return old_fig

@app.callback(
    Output('tsl', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_tsl(n):
    global new_data
    global tsl_list
    global date_list

    table = f"{ticker}-live"
    connection = pymysql.connect(host='localhost',
                             user='root',
                             password=config.DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    connection.autocommit(True)

    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                sql = f"SELECT * FROM `{table}`"
                cursor.execute(sql)
                res = cursor.fetchone()
                live_price = res['price']

    fig = go.Figure()
    print(f'Live Price is {live_price}')
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
            tsl = res0
        avn_list.append(avn)
        print(f"AVN List is {avn_list}")
        # print(f'AVD is {avd}')
        # print(f'AVN is {avn}')
        # print(f'TSL is {tsl}')
        # print(f'Last Price is {live_price}') #
        close_value = new_data.close.tail(1).iloc[0]
        close = float(close_value)

        if live_price > tsl and live_price > close:
            Buy = True  #Crossover of live price over tsl and higher than last candle close
        else:
            Buy = False#
        if live_price < tsl and live_price < close:
            Sell = True #Crossunder of live price under tsl and lower than last candle close
        else:
            Sell = False#
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
                dict(count=150, label="15m", step="minute", stepmode="backward"),
                dict(count=300, label="30m", step="minute", stepmode="backward"),
                dict(count=600, label="1h", step="hour", stepmode="backward"),
                dict(count=1200, label="2h", step="hour", stepmode="backward"),
                dict(step="all")
        ))})
        print(f'TSL Fig is {fig}')
        return fig
    else:
        return {}
    
@app.callback(
    Output('avn', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_avn(n):
    global avn_list
    global date_list

    if avn_list is not None and date_list is not None:
        fig = go.Figure()

        avn = go.Scatter(
            x=date_list,
            y=avn_list,
            mode='lines'
        )

        fig.add_trace(avn)

        fig.update_layout(
            title='AVN',
            yaxis_title='AVN'
        )

        fig.update_xaxes(
            rangeslider_visible=True,
            rangeselector={'buttons': list((
                dict(count=15, label="15m", step="minute", stepmode="backward"),
                dict(count=30, label="30m", step="minute", stepmode="backward"),
                dict(count=1, label="1h", step="hour", stepmode="backward"),
                dict(count=2, label="2h", step="hour", stepmode="backward"),
                dict(step="all")
        ))})
        return fig
    else:
        return {}

if __name__ == '__main__':
    app.run_server(debug=True, port=8080, use_reloader=True)

