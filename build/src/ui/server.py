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
from dash.dependencies import Output, Input, State
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
from pytz import timezone

load_dotenv()

DB_PASS = os.environ.get("DB_PASS")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")
DB_HOST = os.environ.get("DB_HOST")

if DB_HOST is None:
    DB_HOST = "127.0.0.1"

tz = timezone('US/Eastern')
now = datetime.now(tz)

ticker = None
initial_candle = True
last_avd = -1
count = None
date_list = []
tsl_list = []
avn_list = []
new_data = None
first_run = True
last_avn = None
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
    'lionheart': 'cleanandjerks'
}

def fetchTicker():
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    old_ticker = ticker

    #print(f"old_ticker is {old_ticker}")
    table = f"ticker"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            try:
                sql = f"SELECT ticker FROM {table};"
                cursor.execute(sql)
                res = cursor.fetchone()
            except Exception as e:
                log.error(f"Error fetching Ticker: {e}")
            finally:
                cursor.close()
            #log.info(res)

            if ticker is None:
                ticker = res['ticker']
                log.info(f"Set Ticker to {ticker}")
            
            if res['ticker'] is not None and old_ticker != res['ticker']:
                ticker = res['ticker']
                log.info(f"Updated Ticker from {old_ticker} to {ticker}")
            #print(f"Ticker is {ticker}")
        else:
            try:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` (`index` BIGINT,ticker TEXT);"
                cursor.execute(sql)
                result = cursor._last_executed
                print(f"Created: {result}")
            except Exception as e:
                print(f"Error createing Ticker Table: {e}")

            try:
                sql = f"INSERT INTO `{table}` (`index`,ticker) VALUES (0,'{ticker}')"
                cursor.execute(sql)
                result = cursor._last_executed
                print(result)
            except Exception as e:
                print(f"Error inserting into Ticker Table: {e}")
            
            cursor.close()

def sendDiscordMessage(message):
    url = "https://discord.com/api/webhooks/831890918796820510/OWR1HucrnJzHdTE-vASdf5EIbPC1axPikD4D5lh0VBn413nARUW4mla3xPjZHWCK9-9P"
    debug_url = "https://discord.com/api/webhooks/832603152330784819/yA1ZK7ymT3XBU0fJtg0cKZ9RNMPS0C9h0IDABmZZd_KIquToIODOSVOJ6k2aJQSrwC8I"
    webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    if message is None:
        log.warning('Error: Discord Message is empty!')
    else:
        webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
        webhook.send(message)

def checkTableExists(table, cursor):
    try:
        sql = f"SELECT COUNT(*) FROM `{table}`"
        cursor.execute(sql)
        count = cursor.fetchone()
    except Exception as e:
        count = None     
    
    if count is not None and count['COUNT(*)'] > 0:
        return True
    else:
        return False

def dropTables(ticker):
    global database
    global DB_HOST
    global DB_PASS

    tables = (f"{ticker}",
        f"{ticker}-live",
        f"{ticker}-avn",
        f"{ticker}-avd",
        f"{ticker}-tsl",
        f"{ticker}-signal"
    )

    #print(f"Dropping tables {tables}")

    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        for table in tables:
            try:
                sql = f"DROP TABLE `{table}`;"
                res = cursor.execute(sql)
                result = cursor._last_executed
                log.info(f"Dropped Table: {result}")
            except Exception as e:
                log.error(f"Error dropping Table: {e}")
    
    cursor.close()

def updateTicker(ticker):
    global database
    global DB_HOST
    global DB_PASS
    global sup0
    global sup1
    global res0
    global res1
    global live_price
    global last_avn
    global last_avd
    global signal

    sup0 = None
    sup1 = None
    res0 = None
    res1 = None
    live_price = None
    last_avn = None
    last_avd = None
    signal = None

    dropTables(ticker)

    tables = {}

    tables[f"{ticker}"] = {
        "index": "BIGINT PRIMARY KEY",
        "c": "DOUBLE",
        "h": "DOUBLE",
        "l": "DOUBLE",
        "o": "DOUBLE",
        "s": "TEXT",
        "t": "DATETIME",
        "v": "DOUBLE",
    }
    tables[f"{ticker}-live"] = { 
        "id": "INT",
        "price": "FLOAT"
    }
    tables[f"{ticker}-avn"] = {
        "value": "DOUBLE",
        "timestamp": "DATETIME"
    }
    tables[f"{ticker}-avd"] = {
        "value": "DOUBLE",
        "timestamp": "DATETIME"
    }
    tables[f"{ticker}-tsl"] = {
        "value": "DOUBLE",
        "timestamp": "DATETIME"
    }
    tables[f"{ticker}-signal"] = {
        "index": "BIGINT",
        "value": "TEXT"
    }

    #print(f"Creaintg tables {tables}")

    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    for table in tables.keys():
        key_values = ""

        for k in tables[table]:
            val = f"`{k}` {tables[table][k]},"
            key_values = key_values + val


        with connection.cursor() as cursor:
            if not checkTableExists(table, cursor):
                try:
                    sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({key_values[:-1]});"
                    print(sql)
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(f"Created Table: {result}")
                except Exception as e:
                    print(f"Error creating Table: {e}")

            if checkTableExists('ticker', cursor):
                try:
                    sql = f"UPDATE ticker SET ticker = '{ticker}' where `index` = 0"
                    print(sql)
                    result = cursor._last_executed
                    print(f"Updated: {result}")
                    cursor.execute(sql)
                    res = cursor.fetchone()
                except Exception as e:
                    log.error(f"Error updating Ticker: {e}")
                finally:
                    cursor.close()
                log.info(res)

                if res is not None:
                    if ticker is None:
                        ticker = res['ticker']
                        log.info(f"Set Ticker to {ticker}")
                    
                    if res['ticker'] is not None and old_ticker != res['ticker']:
                        ticker = res['ticker']
                        log.info(f"Updated Ticker from {old_ticker} to {ticker}")
                    print(f"Ticker is {ticker}")
            else:
                try:
                    sql = f"CREATE TABLE IF NOT EXISTS {table}` (`index` BIGINT,ticker TEXT);"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(f"Created: {result}")
                except Exception as e:
                    print(f"Error createing Ticker Table: {e}")

                try:
                    sql = f"INSERT INTO `{table}` (`index`,ticker) VALUES (0,'{ticker}')"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(result)
                except Exception as e:
                    print(f"Error inserting into Ticker Table: {e}")
                
                cursor.close()

def fetchSignal():
    global ticker
    global database
    global DB_HOST
    global DB_PASS
    global signal

    table = f"{ticker}-signal"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            log.info("Fetching Signal")
            try:
                sql = f"SELECT (value) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                result = cursor.fetchone()
                signal = result['value']
            except Exception as e:
                log.error(f"Fetch Signal Error: {e}")
            finally:
                cursor.close()

def fetchAvd():
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    avd = {}
    key = "avd"
    table = f"{ticker}-{key}"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            log.info("Fetching AVD")
            try:
                sql = f"SELECT (value) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                values = [item['value'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {values}")
                avd['values'] = values
            except Exception as e:
                log.error(f"Fetch AVD Error: {e}")

            try:
                sql = f"SELECT (timestamp) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                timestamps = [item['timestamp'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {timestamps}")
                avd['timestamps'] = timestamps
            except Exception as e:
                log.error(f"Fetch AVD Error: {e}")

        cursor.close()
        return avd

def fetchAvd():
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    avd = {}
    key = "avd"
    table = f"{ticker}-{key}"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            log.info("Fetching AVD")
            try:
                sql = f"SELECT (value) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                values = [item['value'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {values}")
                avd['values'] = values
            except Exception as e:
                log.error(f"Fetch AVD Error: {e}")

            try:
                sql = f"SELECT (timestamp) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                timestamps = [item['timestamp'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {timestamps}")
                avd['timestamps'] = timestamps
            except Exception as e:
                log.error(f"Fetch AVD Error: {e}")

        cursor.close()
        return avd

def fetchAvn():
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    avn = {}
    key = "avn"
    table = f"{ticker}-{key}"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            log.info("Fetching AVN")
            try:
                sql = f"SELECT (value) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                values = [item['value'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {values}")
                avn['values'] = values
            except Exception as e:
                log.error(f"Fetch AVN Error: {e}")

            try:
                sql = f"SELECT (timestamp) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                timestamps = [item['timestamp'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {timestamps}")
                avn['timestamps'] = timestamps
            except Exception as e:
                log.error(f"Fetch AVN Error: {e}")
        cursor.close()

        return avn

def fetchTsl():
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    tsl = {}
    key = "tsl"
    table = f"{ticker}-{key}"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            log.info("Fetching TSL")
            try:
                sql = f"SELECT (value) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                values = [item['value'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {values}")
                tsl['values'] = values
            except Exception as e:
                log.error(f"Fetch TSL Error: {e}")

            try:
                sql = f"SELECT (timestamp) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                timestamps = [item['timestamp'] for item in cursor.fetchall()]
                #log.info(f"Fetched: {timestamps}")
                tsl['timestamps'] = timestamps
            except Exception as e:
                log.error(f"Fetch TSL Error: {e}")
        
        #print(f"TSL is {tsl}")
        cursor.close()

        return tsl

def fetchLastCandles(dbConnection, ticker):
    try:
        data = pd.read_sql_query(f"SELECT * FROM `{ticker}`", dbConnection);
    except Exception as e:
        raise(e)
    finally:
        dbConnection.close()

    pd.set_option('display.expand_frame_repr', False)
    #print(f"Fetched Table: {data}")

    return data





app = dash.Dash(__name__,suppress_callback_exceptions=True)

server = app.server

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)

def serve_layout():
    return html.Div(children=[
        dcc.Input(
            id="ticker",
            type="text",
            placeholder="Enter Ticker",
        ),
        html.Button('Submit', id='submit-ticker', n_clicks=0),
        html.Div(id='ticker-output',
             children='Enter a value and press submit'),
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
    global DB_HOST
    global DB_PASS
    global live_price

    fetchTicker()

    try:
        sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@{DB_HOST}/{database}', pool_recycle=3600)
    except Exception as e:
        print(f"SQL Engine Error: {e}")

    fig = go.Figure()
    live_table = f"{ticker}-live"

    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    print('meow')
    with sqlEngine.connect() as dbConnection:
        with connection.cursor() as cursor:
            if checkTableExists(live_table, cursor):
                sql = f"SELECT * FROM `{live_table}`"
                cursor.execute(sql)
                res = cursor.fetchone()
                live_price = res['price']
                print(live_price)
        print('woof')
        new_data = fetchLastCandles(dbConnection, ticker)

        fetchSignal()

        print(new_data)
        if new_data is not None:
            candlesticks = go.Candlestick(x=new_data['t'],
                                   open=new_data['o'],
                                   high=new_data['h'],
                                   low=new_data['l'],
                                   close=new_data['c'], name='Market Data')

            fig.add_trace(candlesticks)

            # Add Titles
            fig.update_layout(
                title=ticker + ' Live Price Data',
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
            title='TSL - Either the value of the current Support if AVN is 1, otherwise the Resistance value',
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
        #print(f'TSL Fig is {fig}')
        return fig
    else:
        return {}
    
@app.callback(
    Output('avn', 'figure'),
    [Input('interval-component', 'n_intervals')]
)

def update_avn(n):
    global last_avn

    fig = go.Figure()

    avn = fetchAvn()
    if "values" in avn:
        last_avn = avn["values"][-1]

        if avn is not None and 'timestamps' in avn and 'values' in avn:
            avn = go.Scatter(
                x=avn["timestamps"],
                y=avn["values"],
                mode='lines'
            )

            fig.add_trace(avn)

            fig.update_layout(
                title='AVN - Stores the last non-zero value of AVD.',
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
    else:
        return {}

@app.callback(
    Output('avd', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_avd(n):
    global last_avd

    fig = go.Figure()

    avd = fetchAvd()

    if avd is not None and 'timestamps' in avd and 'values' in avd:
        last_avd = avd["values"][-1]

        avd = go.Scatter(
            x=avd["timestamps"],
            y=avd["values"],
            mode='lines'
        )

        fig.add_trace(avd)

        fig.update_layout(
            title='AVD -  Checks if Live price is below (-1), above(1), or same as the prior candle',
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
    global last_avn
    global last_avd
    global signal

    return [
        html.H1(f'Signal is {signal}', style = {'margin':40}),
        html.H1(f'AVN is {last_avn}', style = {'margin':40}),
        html.H1(f'AVD is {last_avd}', style = {'margin':40}),
        html.H1(f'Last Price is ${live_price}', style = {'margin':40}),
#        html.H1(f'Support 0 is {sup0}', style = {'margin':40}),
#        html.H1(f'Support 1 is {sup1}', style = {'margin':40}),
#        html.H1(f'Resistance 0 is {res0}', style = {'margin':40}),
#        html.H1(f'Resistance 1 is {res1}', style = {'margin':40}),
    ]

@app.callback(
    Output("ticker-output", "children"),
    [Input('submit-ticker', 'n_clicks')],
    [State('ticker', 'value')]
)
def update_ticker(n_clicks,value):
    global ticker
    log.info(value)
    if value is not None:
        ticker = value
        updateTicker(ticker)
        return f"Ticker was {ticker}"
    else:
        return f"Input was empty"

if __name__ == '__main__':
    if DB_PASS is not None or FINNHUB_API_KEY is not None:
        app.run_server(debug=True, port=8080, use_reloader=True)
    else:
        log.error(f"DB_PASS or FINNHUB_API_KEY is not set!")

