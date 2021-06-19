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
import dash_daq as daq
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

db_pass = 'ZVyWpvhexfWyonfFnEvbBozCgChyjoKLgi'
db_user = 'lionheart'
db_host = 'mysql'

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
tsl = None
tsl_value = None

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)

VALID_USERNAME_PASSWORD_PAIRS = {
    'lionheart': 'cleanandjerks'
}

def fetchTicker(ticker, database, db_host, db_pass):
    old_ticker = ticker

    #print(f"old_ticker is {old_ticker}")
    table = 'ticker'
    try:
        connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_pass,
                                 database=database,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 autocommit=True)
    except Exception as e:
        log.error(e)
    else:
        with connection.cursor() as cursor:
            if checkTableExists(table, connection):
                try:
                    sql = f"SELECT ticker FROM {table};"
                    cursor.execute(sql)
                    res = cursor.fetchone()
                except Exception as e:
                    log.error(f"Error fetching Ticker: {e}")
                else:
                    log.info(f"Ticker response was {res}")

                    if 'ticker' in res and res['ticker'] is not 'None':
                        ticker_value = res['ticker']

                    if ticker_value is None:
                        log.error(f"Ticker Value is None")
                    else:
                        if ticker is None and ticker_value:
                            ticker = ticker_value
                            log.info(f"Set Ticker to {ticker}")
                        
                        if old_ticker != ticker_value:
                            ticker = ticker_value
                            log.info(f"Updated Ticker from {old_ticker} to {ticker}")
                        else:
                            log.info(f"Old Ticker: {old_ticker} and New Ticker: {ticker} are the same!")
                    log.info(f"Old Ticker is {old_ticker}")
                finally:
                    cursor.close()
                return ticker
            else:
                if ticker is not None:
                    try:
                        sql = f"CREATE TABLE IF NOT EXISTS `ticker` (`index` BIGINT, ticker TEXT, inverse_trade BOOLEAN, timeframe TEXT, fake_sensitivity BIGINT);"
                        cursor.execute(sql)
                        result = cursor._last_executed
                    except Exception as e:
                        print(f"Error createing Ticker Table: {e}")
                    else:
                        log.info(f"Created Ticker Table: {result}")

                    try:
                        sql = f"INSERT INTO `{table}` (`index`,ticker) VALUES (0,'{ticker}')"
                        cursor.execute(sql)
                        result = cursor._last_executed
                    except Exception as e:
                         log.info(f"Error inserting into Ticker Table: {e}")
                    else:
                        log.info(f"Inserted into Ticker Table: {result}")
                    
                    cursor.close()
                return None

def sendDiscordMessage(message):
    url = "https://discord.com/api/webhooks/831890918796820510/OWR1HucrnJzHdTE-vASdf5EIbPC1axPikD4D5lh0VBn413nARUW4mla3xPjZHWCK9-9P"
    debug_url = "https://discord.com/api/webhooks/832603152330784819/yA1ZK7ymT3XBU0fJtg0cKZ9RNMPS0C9h0IDABmZZd_KIquToIODOSVOJ6k2aJQSrwC8I"
    webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    if message is None:
        log.warning('Error: Discord Message is empty!')
    else:
        webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
        webhook.send(message)

def checkTableExists(table, connection):
    with connection.cursor() as cursor:
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

def dropTables(connection, ticker):

    tables = (f"{ticker}",
        f"{ticker}-live",
        f"{ticker}-avn",
        f"{ticker}-avd",
        f"{ticker}-tsl",
        f"{ticker}-signal"
    )

    with connection.cursor() as cursor:
        for table in tables:
            try:
                sql = f"DROP TABLE `{table}`;"
                res = cursor.execute(sql)
                result = cursor._last_executed
            except Exception as e:
                log.error(f"Error dropping Table: {e}")
            else:
                log.info(f"Dropped Table {table}: {result}")

def updateTicker( database, db_host, db_pass, db_user, new_ticker, inverse_toggle_value, timeframe, fake_sensitivity):
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

    log.info(f"inverse_toggle_value is {inverse_toggle_value}")
    tables = {}

    if new_ticker is not None:
        tables[f"{new_ticker}"] = {
            "index": "BIGINT PRIMARY KEY",
            "c": "DOUBLE",
            "h": "DOUBLE",
            "l": "DOUBLE",
            "o": "DOUBLE",
            "s": "TEXT",
            "t": "DATETIME",
            "v": "DOUBLE",
        }
        tables[f"{new_ticker}-live"] = { 
            "index": "INT",
            "price": "FLOAT"
        }
        tables[f"{new_ticker}-avn"] = {
            "value": "DOUBLE",
            "timestamp": "DATETIME"
        }
        tables[f"{new_ticker}-avd"] = {
            "value": "DOUBLE",
            "timestamp": "DATETIME"
        }
        tables[f"{new_ticker}-tsl"] = {
            "value": "DOUBLE",
            "timestamp": "DATETIME"
        }
        tables[f"{new_ticker}-signal"] = {
            "index": "BIGINT",
            "value": "TEXT"
        }

        try:
            connection = pymysql.connect(host=db_host,
                                     user=db_user,
                                     password=db_pass,
                                     database=database,
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor,
                                     autocommit=True)
        except Exception as e:
            log.error(e)
        else:
            dropTables(connection, new_ticker)

            for table in tables.keys():
                key_values = ""

                for k in tables[table]:
                    val = f"`{k}` {tables[table][k]},"
                    key_values = key_values + val


                with connection.cursor() as cursor:
                    # Create all tables for new Ticker
                    if not checkTableExists(table, connection):
                        try:
                            sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({key_values[:-1]});"
                            log.info(sql)
                            cursor.execute(sql)
                            result = cursor._last_executed
                        except Exception as e:
                            log.error(f"Error creating Table {table}: {e}")
                        else:
                            log.info(f"Created Table {table}: {result}")

                    # Create / Update Ticker table value
                    if checkTableExists('ticker', connection):
                        try:
                            sql = f"UPDATE `ticker` SET ticker = '{new_ticker}', inverse_trade = {inverse_toggle_value}, timeframe = '{timeframe}', fake_sensitivity = '{fake_sensitivity}' where `index` = 0"
                            log.info(sql)
                            result = cursor._last_executed
                            cursor.execute(sql)
                            res = cursor.fetchone()
                        except Exception as e:
                            log.error(f"Error updating Ticker: {e}")
                        else:
                            log.info(f"Updated Ticker table: {new_ticker} with {result}")
                        log.info(res)

                        if res is not None:
                            if new_ticker is None:
                                new_ticker = res['ticker']
                                log.info(f"Set Ticker to {new_ticker}")
                            
                            if res['ticker'] is not None and old_ticker != res['ticker']:
                                new_ticker = res['ticker']
                                log.info(f"Updated Ticker from {old_ticker} to {new_ticker}")
                            print(f"Ticker is {new_ticker}")
                    else:
                        try:
                            sql = f"CREATE TABLE IF NOT EXISTS `ticker` (`index` BIGINT, ticker TEXT, inverse_trade BOOLEAN, timeframe TEXT, fake_sensitivity BIGINT);"
                            log.info(sql)
                            cursor.execute(sql)
                            result = cursor._last_executed
                        except Exception as e:
                            log.error(f"Error creating Ticker Table: {e}")
                        else:
                            log.info(f"Created Ticker table: {result}")

                        try:
                            sql = f"INSERT INTO `ticker` (`index`,ticker) VALUES (0,'{new_ticker}')"
                            log.info(sql)
                            cursor.execute(sql)
                            result = cursor._last_executed
                        except Exception as e:
                            log.error(f"Error inserting into Ticker Table: {e}")
                        else:
                           log.info(f"Inserted Ticker table: {result}")

                        try:
                            sql = f"INSERT INTO `ticker` (`index`,inverse_trade) VALUES (0,{inverse_toggle_value})"
                            log.info(sql)
                            cursor.execute(sql)
                            result = cursor._last_executed
                        except Exception as e:
                            log.error(f"Error inserting Inverse value into Ticker Table: {e}")
                        else:
                           log.info(f"Inserted Inverse value into Ticker table: {result}")
                        
                        cursor.close()

def fetchSignal(connection, ticker):
    global signal

    table = f"{ticker}-signal"

    with connection.cursor() as cursor:
        if checkTableExists(table, connection):
            log.info("Fetching Signal")
            try:
                sql = f"SELECT (value) FROM `{table}`"
                print(sql)
                cursor.execute(sql)
                result = cursor.fetchone()
            except Exception as e:
                log.error(f"Fetch Signal Error: {e}")
            else:
                if 'value' in result:
                    signal = result['value']
            finally:
                cursor.close()

def fetchAvd(ticker, database, db_host, db_pass, db_user):
    avd = {}
    key = "avd"
    table = f"{ticker}-{key}"

    try:
        connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_pass,
                                 database=database,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 autocommit=True)
    except Exception as e:
        log.error(e)
    else:
        with connection.cursor() as cursor:
            if checkTableExists(table, connection):
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

def fetchAvn(ticker, database, db_host, db_pass, db_user):
    avn = {}
    key = "avn"
    table = f"{ticker}-{key}"

    try:
        connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_pass,
                                 database=database,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 autocommit=True)
    except Exception as e:
        log.error(e)
    else:
        with connection.cursor() as cursor:
            if checkTableExists(table, connection):
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

def fetchTsl(ticker, database, db_host, db_pass, db_user):

    tsl = {}
    key = "tsl"
    table = f"{ticker}-{key}"
    try:
        connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_pass,
                                 database=database,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 autocommit=True)
    except Exception as e:
        log.error(e)
    else:
        with connection.cursor() as cursor:
            if checkTableExists(table, connection):
                log.info("Fetching TSL")
                try:
                    sql = f"SELECT (value) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                except Exception as e:
                    log.error(f"Fetch TSL Error: {e}")
                else:
                    values = [item['value'] for item in cursor.fetchall()]
                    #log.info(f"Fetched: {values}")
                    tsl['values'] = values

                try:
                    sql = f"SELECT (timestamp) FROM `{table}`"
                    print(sql)
                    cursor.execute(sql)
                except Exception as e:
                    log.error(f"Fetch TSL Error: {e}")
                else:
                    timestamps = [item['timestamp'] for item in cursor.fetchall()]
                    #log.info(f"Fetched: {timestamps}")
                    tsl['timestamps'] = timestamps

            return tsl

def fetchLastCandles(dbConnection, ticker):
    data = None
    log.info(f"ticker is of NoneType: {isinstance(ticker, type(None))}")
    log.info(f"Ticker is {ticker}")

    if ticker is not None:
        try:
            data = pd.read_sql_query(f"SELECT * FROM `{ticker}`", dbConnection);
        except Exception as e:
            log.error(e)
        finally:
            dbConnection.close()

        pd.set_option('display.expand_frame_repr', False)
        #print(f"Fetched Table: {data}")
        if data is not None:   
            return data

def fetchAlpacaCredentials(database, db_host, db_user, db_pass):
    try:
        connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_pass,
                                 database=database,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 autocommit=True)
    except Exception as e:
        log.error(e)
    else:
        with connection.cursor() as cursor:
            # Create / Update Ticker table value
            if checkTableExists('credentials', connection):
                try:
                    sql = f"SELECT alpaca_key, alpaca_secret FROM `credentials`"
                    cursor.execute(sql)
                    res = cursor.fetchone()
                except Exception as e:
                    log.error(e)
                else:
                    alpaca_key = None
                    alpaca_secret = None

                    if 'alpaca_key' in res:
                        alpaca_key = res['alpaca-key']

                    if 'alpaca_secret' in res:
                        alpaca_secret = res['alpaca_secret']

                    return alpaca_key, alpaca_secret
            else:
                log.error("Credentials Table does not exist!")
                return None, None

def updateAlpacaCredentials(alpaca_key, alpaca_secret, database, db_host, db_user, db_pass):
    try:
        connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_pass,
                                 database=database,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor,
                                 autocommit=True)
    except Exception as e:
        log.error(e)
    else:
        with connection.cursor() as cursor:
            # Create / Update Ticker table value
            if checkTableExists('credentials', connection):
                try:
                    sql = f"UPDATE `credentials` SET alpaca_key = '{alpaca_key}', alpaca_secret = '{alpaca_secret}'"
                    print(sql)
                    result = cursor._last_executed
                    cursor.execute(sql)
                    res = cursor.fetchone()
                except Exception as e:
                    log.error(f"Error updating Credentials: {e}")
                else:
                    log.info(f"Updated Credentials table: {result}")
            else:
                try:
                    sql = f"CREATE TABLE IF NOT EXISTS `credentials` (alpaca_key TEXT, alpaca_secret TEXT);"
                    log.info(log.info)
                    cursor.execute(sql)
                    result = cursor._last_executed
                except Exception as e:
                    log.error(f"Error creating Credentials Table: {e}")
                else:
                    log.info(f"Created Credentials table: {result}")

                try:
                    sql = f"INSERT INTO `credentials` (alpaca_key, alpaca_secret) VALUES ('{alpaca_key}','{alpaca_secret}')"
                    print(sql)
                    cursor.execute(sql)
                    result = cursor._last_executed
                except Exception as e:
                    log.error(f"Error inserting into Credentials Table: {e}")
                else:
                   log.info(f"Inserted Credentials table: {result}")
                
                cursor.close()

app = dash.Dash(__name__,suppress_callback_exceptions=True)

server = app.server

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)

def serve_layout():
    return html.Div(children=[
        html.Div([
            dcc.Input(
                id="new-ticker",
                type="text",
                placeholder="Enter Ticker",
            ),
            dcc.RadioItems(
                id="timeframe-input",
                options=[
                    {'label': '1m', 'value': '1'},
                    {'label': '5m', 'value': '5'},
                    {'label': '15m', 'value': '15'},
                    {'label': '30m', 'value': '30'},
                    {'label': '1 Hour', 'value': '60'},
                    {'label': '1 Day', 'value': 'D'}
                ],
                value=None
            ),
            dcc.RadioItems(
                id="fake-sensitivity",
                options=[
                    {'label': 'Conservative', 'value': '0'},
                    {'label': 'Moderate', 'value': '1'},
                    {'label': 'Liberal', 'value': '2'}
                ],
                value=None
            ),
            dcc.RadioItems(
                id="submit-inverse-toggle",
                options=[
                    {'label': 'Regular', 'value': 'False'},
                    {'label': 'Inverse', 'value': 'True'},
                ],
                value=None
            ),
            html.Button('Submit', id='submit-ticker', n_clicks=0),
            html.Div(id='ticker-output',
                children='Select your parameters'),

        ], style={}, id='input-container'),
        html.Div([
            dcc.Input(
                id="alpaca-key",
                type="text",
                placeholder="Alpaca API Key",
            ),
            dcc.Input(
                id="alpaca-secret",
                type="text",
                placeholder="Alpaca API Secret",
            ),
            html.Button('Submit', id='submit-alpaca', n_clicks=0),
            html.Div(id='alpaca-output',
                 children='Enter a your Alpaca API Key and Secret'),
        ], style={}, id='alpaca-input'),   
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
        dcc.Store(id='ticker-value')
        ])

app.layout = serve_layout

@app.callback(
    Output('candles', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_candles(n):
    global old_fig
    global ticker
    global database
    global new_data
    global db_host
    global db_pass
    global live_price

    ticker = fetchTicker(ticker, database, db_host, db_pass)

    log.info(f"ticker is of NoneType: {isinstance(ticker, type(None))}")
    log.info(f"Ticker is { ticker}")

    if ticker is not None:
        try:
            sqlEngine = create_engine(f'mysql+pymysql://{db_user}:{db_pass}@{db_host}/{database}', pool_recycle=3600)
        except Exception as e:
            log.error(f"SQL Engine Error: {e}")
        else:
            fig = go.Figure()
            live_table = f"{ticker}-live"

            connection = pymysql.connect(host=db_host,
                                     user=db_user,
                                     password=db_pass,
                                     database=database,
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor,
                                     autocommit=True)
            with sqlEngine.connect() as dbConnection:
                new_data = fetchLastCandles(dbConnection, ticker)

                fetchSignal(connection, ticker)

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
    else:
        return {}

@app.callback(
    Output('tsl', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_tsl(n):
    global database
    global db_host
    global db_pass
    global db_user
    global tsl

    fig = go.Figure()

    tsl = fetchTsl(ticker, database, db_host, db_pass, db_user)

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
        return fig
    else:
        return {}
    
@app.callback(
    Output('avn', 'figure'),
    [Input('interval-component', 'n_intervals')]
)

def update_avn(n):
    global database
    global db_host
    global db_pass
    global last_avn

    avn = None
    fig = go.Figure()

    avn = fetchAvn(ticker, database, db_host, db_pass, db_user)

    fig.update_layout(
        title='AVN - Stores the last non-zero value of AVD.',
        yaxis_title='AVN'
    )

    if avn is not None and "values" in avn:
        last_avn = avn["values"][-1]

        if avn is not None and 'timestamps' in avn and 'values' in avn:
            avn = go.Scatter(
                x=avn["timestamps"],
                y=avn["values"],
                mode='lines'
            )

            fig.add_trace(avn)



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
            return fig
    else:
        return fig

@app.callback(
    Output('avd', 'figure'),
    [Input('interval-component', 'n_intervals')]
)
def update_avd(n):
    global database
    global db_host
    global db_pass
    global last_avd
    avd = None
    fig = go.Figure()

    avd = fetchAvd(ticker, database, db_host, db_pass, db_user)

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
    global tsl
    global tsl_value
    global ticker

    if tsl is not None and 'y' in tsl:
        log.info(f"tsl is {tsl['y'][-1]}")
        tsl_value = tsl['y'][-1]

    return [
        html.H1(f'Ticker is {ticker}', style = {'margin':40}),
        html.H1(f'Signal is {signal}', style = {'margin':40}),
        html.H1(f'AVN is {last_avn}', style = {'margin':40}),
        html.H1(f'AVD is {last_avd}', style = {'margin':40}),
        html.H1(f'Last Price is ${live_price}', style = {'margin':40}),
        html.H1(f'TSL is ${tsl_value}', style = {'margin':40}),
#        html.H1(f'Support 0 is {sup0}', style = {'margin':40}),
#        html.H1(f'Support 1 is {sup1}', style = {'margin':40}),
#        html.H1(f'Resistance 0 is {res0}', style = {'margin':40}),
#        html.H1(f'Resistance 1 is {res1}', style = {'margin':40}),
    ]

@app.callback(
    Output("input-container", "style"),
    Output("ticker-output", "children"),
    Input('submit-ticker', 'n_clicks'),
    State('new-ticker', 'value'),
    State('submit-inverse-toggle', 'value'),
    State('timeframe-input', 'value'),
    State('fake-sensitivity', 'value')
)
def update_ticker(n_clicks, new_ticker, inverse_toggle_value_input, timeframe, fake_sensitivity):
    global ticker
    log.info(f"new_ticker is {new_ticker}")
    log.info(f"inverse_toggle_value_input is {inverse_toggle_value_input}")
    log.info(f"timeframe is {timeframe}")
    log.info(f"fake_sensitivity is {fake_sensitivity}")

    if new_ticker is None:
        return {'display': 'block'}, f"Ticker is required"

    if inverse_toggle_value_input is None:
        return {'display': 'block'}, f"Inverse Toggle is required"

    if timeframe is None:
        return {'display': 'block'}, f"Timeframe is required"

    if fake_sensitivity is None:
        return {'display': 'block'}, f"Fake Sensitivity is required"

    if inverse_toggle_value_input is not None and inverse_toggle_value_input == 'True':
        inverse_toggle_value = True
    else:
        inverse_toggle_value = False

    if new_ticker is not None and inverse_toggle_value is not None and timeframe is not None and inverse_toggle_value is not None and fake_sensitivity is not None:
        ticker = new_ticker
        updateTicker(database, db_host, db_pass, db_user, new_ticker, inverse_toggle_value, timeframe, fake_sensitivity)
        return {'display': 'none'}, ''
    else:
        return {'display': 'block'}, ''

@app.callback(
    Output("alpaca-output", "children"),
    Output('alpaca-input', 'style'),
    Input('submit-alpaca', 'n_clicks'),
    State('alpaca-key', 'value'),
    State('alpaca-secret', 'value'),
)
def update_alpaca_api(n_clicks, alpaca_key, alpaca_secret):
    global ticker
    global database
    global db_host
    global db_pass

    alpaca_key, alpaca_secret = fetchAlpacaCredentials(database, db_host, db_user, db_pass)

    if alpaca_key is not None and alpaca_secret is not None:
        return '', {'display': 'none'}
    else:
        log.info(f"Alpaca API Key is {alpaca_key}")
        log.info(f"Alpaca API Secret is {alpaca_secret}")

        if alpaca_key is None:
            log.error(f"Alpaca API Key is not set")
            return f"Alpaca API Key is required", {'display': 'block'}

        if alpaca_secret is None:
            log.error(f"Alpaca API Secret is not set")
        
            return f"Alpaca API Secret is required", {'display': 'block'}

        updateAlpacaCredentials(alpaca_key, alpaca_secret, database, db_host, db_user, db_pass)

if __name__ == '__main__':
    load_dotenv()

    db_pass = os.environ.get("MYSQL_PASSWORD")

    finnhub_api_key = os.environ.get("FINNHUB_API_KEY")

    if db_pass is None:
        log.error(f"db_pass is not set!")
    elif finnhub_api_key is None:
        log.error(f"finnhub_api_key is not set!")
    else:
        app.run_server(debug=False, port=8080, use_reloader=False)


