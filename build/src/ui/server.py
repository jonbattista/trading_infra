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
from dash.dependencies import Output, Input
from sqlalchemy import create_engine
import pymysql.cursors
import logging
from sys import stdout
import mysql.connector as sql
from discord import Webhook, RequestsWebhookAdapter
import pandas as pd
from dotenv import load_dotenv
import dash_auth
import os

load_dotenv()

DB_PASS = os.environ.get("DB_PASS")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")

#host = "mysql-server.default.svc.cluster.local"
host = "127.0.0.1"
now = datetime.now(timezone('UTC'))

ticker = 'BINANCE:BTCUSDT'
initial_candle = True
avd = -1
count = None
date_list = []
tsl_list = []
avn_list = []
new_data = None
first_run = True
avn = None
previous_avd = 0
live_price = None
data = None
last_minute = None
database = "trades"
old_fig = {}
tsl_array=[]
sup0 = 0
sup1 = 0
res0 = 0
res1 = 0
signal = None
log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)

VALID_USERNAME_PASSWORD_PAIRS = {
    'jonbattista': 'test'
}

def sendDiscordMessage(message):
    url = "https://discord.com/api/webhooks/831890918796820510/OWR1HucrnJzHdTE-vASdf5EIbPC1axPikD4D5lh0VBn413nARUW4mla3xPjZHWCK9-9P"
    debug_url = "https://discord.com/api/webhooks/832603152330784819/yA1ZK7ymT3XBU0fJtg0cKZ9RNMPS0C9h0IDABmZZd_KIquToIODOSVOJ6k2aJQSrwC8I"
    webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    if message is None:
        log.warning('Error: Discord Message is empty!')
    else:
        webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
        webhook.send(message)

def dropTables():
    global ticker
    global database
    global host
    global first_run

    if first_run:
        first_run = False
        tables = (f"{ticker}-live",f"{ticker}-avn",f"{ticker}-avd",f"{ticker}-tsl")
        print(tables)
        connection = pymysql.connect(host=host,
                                 user='root',
                                 password=DB_PASS,
                                 database=database,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 autocommit=True)
        with connection:
            with connection.cursor() as cursor:
                for table in tables:
                    try:
                        sql = f"DROP TABLE `{table}`;"
                        res = cursor.execute(sql)
                        result = cursor._last_executed
                        log.info(f"Dropped Table: {result}")
                    except Exception as e:
                        log.error(f"Drop Table Error: {e}")
        
                cursor.close()

def updateAvd(value,timestamp):
    global ticker
    global database
    global host

    kind = "avd"

    keys = ("value","timestamp")
    table = f"{ticker}-{kind}"
    connection = pymysql.connect(host=host,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                try:
                    sql = f"INSERT INTO `{table}` ({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}');"
                    res = cursor.execute(sql)
                    result = cursor._last_executed
                    log.info(f"Update: {result}")
                except Exception as e:
                    log.error(f"Update AVD Error: {e}")
                finally:
                    cursor.close()
            else:
                try:
                    sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({keys[0]} DOUBLE,{keys[1]} DATETIME);"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(f"Create: {result}")
                except Exception as e:
                    print(f"Create AVD Error: {e}")

                try:
                    sql = f"INSERT INTO `{table}`({keys[0]},{keys[1]}) values ({value},'{timestamp}')"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(result)
                except Exception as e:
                    print(f"Insert AVD Error: {e}")
                finally:
                    cursor.close()
def fetchAvd():
    global ticker
    global database
    global host

    avd = {}
    key = "avd"
    table = f"{ticker}-{key}"
    connection = pymysql.connect(host=host,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                log.info("Fetching AVD")
                try:
                    sql = f"SELECT (value) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                    values = [item['value'] for item in cursor.fetchall()]
                    log.info(f"Fetched: {values}")
                    avd['values'] = values
                except Exception as e:
                    log.error(f"Fetch AVD Error: {e}")

                try:
                    sql = f"SELECT (timestamp) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                    timestamps = [item['timestamp'] for item in cursor.fetchall()]
                    log.info(f"Fetched: {timestamps}")
                    avd['timestamps'] = timestamps
                except Exception as e:
                    log.error(f"Fetch AVD Error: {e}")
            print(avd)
            cursor.close()
            return avd

def updateAvn(value,timestamp):
    global ticker
    global database
    global host

    kind = "avn"

    keys = ("value","timestamp")
    table = f"{ticker}-{kind}"
    connection = pymysql.connect(host=host,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor) and avn is not None:
                try:
                    sql = f"INSERT INTO `{table}` ({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}');"
                    res = cursor.execute(sql)
                    result = cursor._last_executed
                    log.info(f"Update: {result}")
                except Exception as e:
                    log.error(f"Update AVN Error: {e}")
                finally:
                    cursor.close()
            else:
                try:
                    sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({keys[0]} DOUBLE,{keys[1]} DATETIME);"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(f"Create: {result}")
                except Exception as e:
                    print(f"Create AVN Error: {e}")
                if avn is not None:
                    try:
                        sql = f"INSERT INTO `{table}` ({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}');"
                        print(sql)
                        cursor.execute(sql)
                        result = cursor._last_executed
                        print(result)
                    except Exception as e:
                        print(f"Insert AVN Error: {e}")
                    finally:
                        cursor.close()
def fetchAvn():
    global ticker
    global database
    global host

    avn = {}
    key = "avn"
    table = f"{ticker}-{key}"
    connection = pymysql.connect(host=host,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                log.info("Fetching AVN")
                try:
                    sql = f"SELECT (value) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                    values = [item['value'] for item in cursor.fetchall()]
                    log.info(f"Fetched: {values}")
                    avn['values'] = values
                except Exception as e:
                    log.error(f"Fetch AVN Error: {e}")

                try:
                    sql = f"SELECT (timestamp) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                    timestamps = [item['timestamp'] for item in cursor.fetchall()]
                    log.info(f"Fetched: {timestamps}")
                    avn['timestamps'] = timestamps
                except Exception as e:
                    log.error(f"Fetch AVN Error: {e}")
            print(avn)
            cursor.close()
            return avn

def updateTsl(value,timestamp):
    global ticker
    global database
    global host

    kind = "tsl"
    keys = ("value","timestamp")
    table = f"{ticker}-{kind}"
    connection = pymysql.connect(host=host,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                try:
                    sql = f"INSERT INTO `{table}` ({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}');"
                    res = cursor.execute(sql)
                    result = cursor._last_executed
                    log.info(f"Update: {result}")
                except Exception as e:
                    log.error(f"Update TSL Error: {e}")
                finally:
                    cursor.close()
            else:
                try:
                    sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({keys[0]} DOUBLE,{keys[1]} DATETIME);"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(f"Create: {result}")
                except Exception as e:
                    print(f"Create TSL Error: {e}")

                try:
                    sql = f"INSERT INTO `{table}`({keys[0]},{keys[1]}) values ({value},'{timestamp}')"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(result)
                except Exception as e:
                    print(f"Insert TSL Error: {e}")
                finally:
                    cursor.close()
def fetchTsl():
    global ticker
    global database
    global host

    tsl = {}
    key = "tsl"
    table = f"{ticker}-{key}"
    connection = pymysql.connect(host=host,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                log.info("Fetching TSL")
                try:
                    sql = f"SELECT (value) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                    values = [item['value'] for item in cursor.fetchall()]
                    log.info(f"Fetched: {values}")
                    tsl['values'] = values
                except Exception as e:
                    log.error(f"Fetch TSL Error: {e}")

                try:
                    sql = f"SELECT (timestamp) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                    timestamps = [item['timestamp'] for item in cursor.fetchall()]
                    log.info(f"Fetched: {timestamps}")
                    tsl['timestamps'] = timestamps
                except Exception as e:
                    log.error(f"Fetch TSL Error: {e}")
            
            print(f"TSL is {tsl}")
            cursor.close()
            return tsl

def checkTables(table, cursor):
    stmt = "SHOW TABLES LIKE '%s' "% ('%'+str(table)+'%')
    cursor.execute(stmt)
    result = cursor.fetchone()         
    return result

def calcTsl(data):
    global previous_avd
    global sup0
    global sup1
    global res0
    global res1
    global live
    global avn
    global avd
    global signal

    fig = go.Figure()

    table = f"{ticker}-live"
    connection = pymysql.connect(host=host,
                             user='root',
                             password=DB_PASS,
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
                live = res['price']

    if data is not None and live is not None:
        print(f'Live Price is {live}')
        print(f'TSL New Data is {data}')
        now_utc = pytz.utc.localize(datetime.utcnow())
        now_est = now_utc.astimezone(pytz.timezone("America/New_York"))
        now_est = now_est.strftime('%Y-%m-%d %H:%M:%S.%f')#
        high = data.h
        #print(tsl_ts)
        #print(high)#
        last3H0 = high.tail(3)  # last 3 including active candle [0]
        last3H1 = high.tail(4).head(3)  # last 3 not including active [1]
        # print(last3H1)#
        low = data.l
        # print(low)#
        low3H0 = low.tail(3)  # last 3 including active candle [0]
        low3H1 = low.tail(4).head(3)  # last 3 not including active [1]
        # print(low3H1)##
        res0 = float(max(last3H0))  # MAX of prior including active [0]
        res1 = float(max(last3H1))#
        sup0 = float(min(low3H0))  # Min of prior including active [0]
        sup1 = float(min(low3H1))

        # AVD - Checks is live value is below or above prior candle
        # support/resistance
        if live > res1:
            avd = 1
        elif live < sup1:
            avd = -1
        else:
            avd = 0

        if avd != previous_avd:
            #sendDiscordMessage(f'AVD changed from {previous_avd} to {avd}!')
            previous_avd = avd
        print(f'AVD is {avd}')
        if avd is not None:
            updateAvd(avd,now_est)

        # AVN  - AVD value of last non-zero condition stored.
        if avd != 0:
            avn = avd
            updateAvn(avn,now_est)
        print(f'AVN is {avn}')

        # TSL line
        if avn == 1:
            tsl = sup0
        else:
            tsl = res0

        print(f'TSL is {tsl}')
        if tsl is not None:
            updateTsl(tsl,now_est)

        close_value = data.c.tail(1).iloc[0]
        close = float(close_value)

        if live > tsl and live > close:
            Buy = True  #Crossover of live price over tsl and higher than last candle close
            print(f'Crossover Buy is True')
            signal = 'Buy'
        else:
            Buy = False
            print(f'Crossover Buy is False')
        if live < tsl and live < close:
            Sell = True #Crossunder of live price under tsl and lower than last candle close
            print(f'Crossover Sell is True')
            signal = 'Sell'
        else:
            Sell = False
            print(f'Crossover Sell is False')

def fetchLastCandles(dbConnection):
    try:
        data = pd.read_sql_query(f"select * from `{ticker}`", dbConnection);
    except Exception as e:
        raise(e)
    dbConnection.close()

    pd.set_option('display.expand_frame_repr', False)
    print(f"Fetched Table: {data}")
    return data

app = dash.Dash(__name__,suppress_callback_exceptions=True)

server = app.server

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)

def serve_layout():
    return html.Div(children=[
        dcc.Graph(id = 'candles'),
        html.Div(id='metrics', style = {'display': 'flex', 'align-items': 'center', 'justify-content': 'center'}),
        html.Div([
            html.Div([
                dcc.Graph(id = 'tsl'),
            ], className='six columns'),
            html.Div([
                dcc.Graph(id = 'avn'),
            ], className='six columns'),
            html.Div([
                dcc.Graph(id = 'avd'),
            ], className='six columns')
        ], className='row'),

        dcc.Interval(
            id = 'interval-component',
            interval = 2*1000,
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
    global host
    global DB_PASS

    print('meow')
    try:
        sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@{host}/{database}', pool_recycle=3600)
    except Exception as e:
        print(f"SQL Engine Error: {e}")

    connection = sqlEngine.raw_connection()
    cursor = connection.cursor()
    dbConnection = sqlEngine.connect()

    fig = go.Figure()
    print('woof')
    new_data = fetchLastCandles(dbConnection)
    
    log.info(new_data)
    if new_data is not None:
        calcTsl(new_data)

        candlesticks = go.Candlestick(x=new_data['t'],
                               open=new_data['o'],
                               high=new_data['h'],
                               low=new_data['l'],
                               close=new_data['c'], name='Market Data')

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
    fig = go.Figure()

    tsl = fetchTsl()

    if tsl is not None and 'timestamps' in tsl and 'values' in tsl:
        tsl = go.Scatter(
                x=tsl['timestamps'],
                y=tsl['values'],
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
    fig = go.Figure()

    avn = fetchAvn()

    if avn is not None and 'timestamps' in avn and 'values' in avn:
        avn = go.Scatter(
            x=avn["timestamps"],
            y=avn["values"],
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

@app.callback(
    Output('avd', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_avd(n):
    fig = go.Figure()

    avd = fetchAvd()
    print(avd)
    if avd is not None and 'timestamps' in avd and 'values' in avd:
        avd = go.Scatter(
            x=avd["timestamps"],
            y=avd["values"],
            mode='lines'
        )

        fig.add_trace(avd)

        fig.update_layout(
            title='AVD',
            yaxis_title='AVD'
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

@app.callback(
    Output('metrics', 'children'),
    [Input('interval-component', 'n_intervals')]
)
def update_metrics(n):
    global sup0
    global sup1
    global res0
    global res1
    global live_price
    global avn
    global avd
    global signal

    return [
        html.H1(f'Signal is {signal}', style = {'margin':40}),
        html.H1(f'AVN is {avn}', style = {'margin':40}),
        html.H1(f'AVD is {avd}', style = {'margin':40}),
        html.H1(f'Last Price is ${live_price}', style = {'margin':40}),
        html.H1(f'Support 0 is {sup0}', style = {'margin':40}),
        html.H1(f'Support 1 is {sup1}', style = {'margin':40}),
        html.H1(f'Resistance 0 is {res0}', style = {'margin':40}),
        html.H1(f'Resistance 1 is {res1}', style = {'margin':40}),
    ]

if __name__ == '__main__':
    dropTables()
    app.run_server(debug=True, port=8080, use_reloader=True)

