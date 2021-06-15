import ssl
import json
import sched
from sqlalchemy import create_engine
import pymysql.cursors
import pandas as pd
from datetime import datetime
import time 
import multiprocessing
import logging
from sys import stdout
import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
import os
from pytz import timezone, utc
import websocket
from time import sleep
from discord import Webhook, RequestsWebhookAdapter

tz = timezone('US/Eastern')
now = datetime.now(tz)

initial_candle = True
avd = None
count = None
date_list = []
tsl_list = []
avn_list = []
new_data = None
first_run = True
avn = None
previous_avd = 0
data = None
last_minute = None
database = "trades"
tsl_array=[]
sup0 = 0
sup1 = 0
res0 = 0
res1 = 0
signal = None
buy_signal_count = 0
sell_signal_count = 0
check_buy_signal = False
check_sell_signal = False
buy_signal_flag = False
sell_signal_flag = False
signal_count_limit = 0
inverse_trade = False
live = None

inverse_table = {
    'TQQQ': 'SQQQ',
    'SPXL': 'SPXS',
    'SOXL': 'SOXS',
    'FNGU': 'FNGD',
    'GUSH': 'DRIP',
    'LABU': 'LABD',
    'BINANCE:BTCUSDT': 'CTB'
}

VALID_USERNAME_PASSWORD_PAIRS = {
    'lionheart': 'cleanandjerks'
}

load_dotenv()

APCA_API_KEY_ID = 'PK1DW9PYFTSM2IC6XYYL'
APCA_API_SECRET_KEY = 'FFDPNjs3aqGL3iXx0bixL167gXPSxkGqQEIrLkQh'

db_pass = os.environ.get("DB_PASS")
finnhub_api_key = os.environ.get("FINNHUB_API_KEY")

db_host = os.environ.get("DB_HOST")

if db_host is None:
    db_host = "127.0.0.1"

db_user = 'root'
ticker = None
database = "trades"
timeframe = None
first_run = True

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)

def checkTableExists(table, cursor):
    try:
        sql = f"SELECT COUNT(*) FROM `{table}`"
        cursor.execute(sql)
        res = cursor.fetchone()
    except Exception as e:
        log.error(e)
    else:
        #log.info(f"Table Count is {count}")
        if res is not None and 'COUNT(*)' in res and res['COUNT(*)'] > 0:
            return True
        else:
            log.info(f"Table {table} is empty or does not exist")
            return False

def fetchTicker(ws, database, db_user, db_pass, db_host):
    global ticker

    old_ticker = ticker

    table = "ticker"

    connection = pymysql.connect(host=db_host,
                             user=db_user,
                             password=db_pass,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            try:
                sql = f"SELECT ticker, timeframe, fake_sensitivity FROM {table};"
                cursor.execute(sql)
                res = cursor.fetchone()
            except Exception as e:
                log.error(f"Error fetching Ticker: {e}")
            else:
                log.info(f"Trade Parameters are {res}")

                if ticker is None:
                    ticker = res['ticker']
                    log.info(f"Setting Ticker to {ticker}")
            
                if 'ticker' in res and res['ticker'] is not None and old_ticker != res['ticker']:
                    ticker = res['ticker']
                    log.info(f"Updated Ticker from {old_ticker} to {ticker}")
                    log.info("Ticker changed. Updating Websocket...")

                if 'timeframe' in res and res['timeframe'] is not None:
                    timeframe = res['timeframe']

                if 'fake_sensitivity' in res and res['fake_sensitivity'] is not None:
                    fake_sensitivity = res['fake_sensitivity']

                if 'inverse_trade' in res and res['inverse_trade'] == 1:
                    use_inverse_trade = True
                else:
                    use_inverse_trade = False
                
                log.info(f"Ticker is {ticker}")
                log.info(f"Timeframe is {timeframe}")
                log.info(f"Fake Sensitivity is {fake_sensitivity}")
                log.info(f"Use Inverse Trade is {use_inverse_trade}")

                return ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker

            finally:
                cursor.close()
            
        else:
            try:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` (`index` BIGINT, ticker TEXT, inverse_trade BOOLEAN, timeframe TEXT, fake_sensitivity BIGINT);"
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


def buildCandleDataFrame(ticker, database, db_user, db_pass, db_host, timeframe, live):

    sqlEngine = create_engine(f'mysql+pymysql://{db_user}:{db_pass}@{db_host}/{database}', pool_recycle=3600)

    connection = pymysql.connect(host=db_host,
                         user=db_user,
                         password=db_pass,
                         database=database,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor,
                         autocommit=True)
    with connection.cursor() as cursor:
        with sqlEngine.connect() as dbConnection:
            if checkTableExists(ticker,cursor):
                try:
                    data = pd.read_sql(f"SELECT * FROM `{ticker}`", dbConnection);
                except Exception as e:
                    log.error(e)
                else:
                    if len(data.index) > 0:

                        while len(data.index) > 5:
                            i = data.index[0]
                            data = data.drop(i)
                            log.info(f"Dropped Dataframe Row at index: {i}")

                    index = len(data.index) 
                    #print(df_len)
                    log.info(data)
                    log.info(f"Dataframe Size is {index}")

                    open_value = round(data['o'].iloc[-1], 2)
                    high_value = round(data['h'].iloc[-1], 2)
                    low_value = round(data['l'].iloc[-1], 2)
                    close_value = round(data['c'].iloc[-1], 2)

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

                    tz = timezone('US/Eastern')
                    #date = datetime.now(tz)
                    now_utc = utc.localize(datetime.utcnow())
                    print(f"Now UTC is {now_utc}")
                    now_est = now_utc.astimezone(tz)
                    print(f"Now EST is {now_est}")

                    try:
                        #log.info(f"Previous is {data.at[index - 1, 't']}")
                        previous_time = data.at[index -1,'t'].to_pydatetime()
                    except Exception as e:
                        log.error(e)
                    else:
                        print(f"T is {previous_time}")
                    #previous_timeframe = None
                    #current_timeframe = None
                    print('bark')
                    print(f"Websocket Timeframe is {timeframe}")

                    if timeframe is not None:
                        log.info('meow')
                        if timeframe == '1':
                            previous_timeframe = previous_time.minute
                            current_timeframe = now_est.minute
                            current_timeframe_string = now_est.strftime('%Y-%m-%d %H:%M:00')
                        elif timeframe == '5':
                            previous_timeframe = previous_time.minute
                            current_timeframe = now_est.minute
                            if current_minute.minute % 5 == 0:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:%M:00')
                            else:
                                minute = 5 * round(current_minute.minute/5)
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:{minute}:00')
                        elif timeframe == '15':
                            previous_timeframe = previous_time.day
                            current_timeframe = now_est.day
                            if current_minute.minute % 15 == 0:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:%M:00')
                            else:
                                minute = 15 * round(current_minute.minute/15)
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:{minute}:00')
                        elif timeframe == '30':
                            previous_timeframe = previous_time.minute
                            current_timeframe = now_est.minute
                            if current_minute.minute < 30:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:00:00')
                            else:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:30:00')
                        elif timeframe == '60':
                            previous_timeframe = previous_time.hour
                            current_timeframe = now_est.hour
                            current_timeframe_string = now_est.strftime('%Y-%m-%d %H:00:00')
                        elif timeframe == 'D':
                            previous_timeframe = previous_time.day
                            current_timeframe = now_est.day
                            current_timeframe_string = now_est.strftime('%Y-%m-%d 20:00:00')

                        log.info(f"Previous Timeframe is {previous_timeframe}")
                        log.info(f"Current Timeframe is {current_timeframe}")

                        # If the current timeframe value is different from the previous timeframe value
                        # then add it to the table
                        #if previous_timeframe != current_timeframe:
#                            data.at[index,'index']=index
#                            data.at[index,'o']=open_value
#                            data.at[index,'h']=high_value
#                            data.at[index,'l']=low_value
#                            data.at[index,'c']=close_value
#                            data.at[index,'v']=0
#                            data.at[index,'t']=current_timeframe_string

#                            values = ""

#                            for k, v in zip(data.columns.tolist(), tuple(data.iloc[index - 1])):
#                                #print(k)
#                                #print(v)
#                                if k != "index":
#                                    #values = values + f"'{v}', "
#                                    values = values + f"`{k}` = '{v}', "

                            #values = values[:-2]
                            #values = f"'{close_value}', '{high_value}', '{low_value}', '{open_value}', 'ok', '{current_timeframe_string}', {0}"
                        values = f"`c` = '{close_value}', `h` = '{high_value}', `l` = '{low_value}', `o` = '{open_value}', `s` = 'ok', `t` = '{current_timeframe_string}', `v` = '0.0'"
                        
                        log.info(f"Values are: {values}")

                        try:
                            #sql = f"INSERT INTO `{ticker}` VALUES ({index+1}, {values})"
                            sql = f"UPDATE `{ticker}` SET {values} WHERE `index` = {index}"
                            log.info(sql)
                            cursor.execute(sql)
                        except Exception as e:
                            log.info(e)
                        else:
                            log.info(f"Successfully added row {values} to table {ticker}")
                            log.info(f"Rows Modified = {cursor.rowcount}")
                        # If the current timeframe value is the same as the previous timeframe value
                        # and the Close price is different, then update the table row
                        #else:

#                            data.at[index,'index']=index
#                            data.at[index,'o']=open_value
#                            data.at[index,'h']=high_value
#                            data.at[index,'l']=low_value
#                            data.at[index,'c']=close_value
#                            data.at[index,'v']=0
#                            data.at[index,'t']=current_timeframe_string

#                            log.info(data)
#                            cols = "`,`".join([str(i) for i in data.columns.tolist()])
                            #print(f"Columns: {cols}")

                            # Insert DataFrame recrds one by one.
#                            for i,row in data.iterrows():
#                                #print(f"index: {i}")
#                                #print(f"Row: {row}")
#                                #values = "`,`".join([str(i) for i in row])
#                                #print(values)
#                                keys = ""#

#                                for k, v in zip(data.columns.tolist(), tuple(row)):
#                                    #print(k)
#                                    #print(v)
#                                    if k != "index":
#                                        keys = keys + f"`{k}` = '{v}', "#

#                                keys = keys[:-2]
#                                log.info(f"Keys are: {keys}")#
#                                values = f"`c` = '{close_value}', `h` = '{high_value}', `l` = '{low_value}', `o` = '{open_value}', `s` = 'ok', `t` = '{current_timeframe_string}', `v` = '0.0'"
#                            
#                                log.info(f"Values are: {values}")

#                                try:
#                                    sql = f"UPDATE `{ticker}` SET {keys} WHERE `index` = {index}"
#                                    cursor.execute(sql)
#                                except Exception as e:
#                                    log.info(e)
#                                else:
#                                    log.info(f"Successfully updated table {ticker} with value {keys}")
#                                    log.info(f"Rows Modified = {cursor.rowcount}")
#                            try:
#                                new_table = pd.read_sql(f"SELECT * FROM `{ticker}`", dbConnection);
#                            except Exception as e:
#                                log.info(e)#

#                            pd.set_option('display.expand_frame_repr', False)
#                            
#                            log.info(f"Updated Table is {new_table}")
#                            cursor.close()

                    else:
                        log.error("Timeframe is not set!")
            else:
                log.error(f"Error: Table {ticker} does not exist or is empty!")
                log.error(f"It will be created on next Historical Job run.")

def updateLatestPrice(database, db_user, db_pass, db_host, price):
    table = f"{ticker}-live"
    connection = pymysql.connect(host=db_host,
                             user=db_user,
                             password=db_pass,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table,cursor):
            try:
                sql = f"UPDATE `{table}` SET `price` = {price} WHERE `index` = 0"
                print(sql)
                res = cursor.execute(sql)
                result = cursor._last_executed
                log.info(f"Updated Live Price column: {result}")
            except Exception as e:
                log.error(f"Error updating Live Price column: {e}")
            finally:
                cursor.close()
        else:
            try:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` (`index` INT PRIMARY KEY, price FLOAT);"
                log.info(sql)
                cursor.execute(sql)
                result = cursor._last_executed
            except Exception as e:
                log.error(f"Error creating Live Price Table: {e}")
            else:
                log.info(f"Created Live Price Table: {result}")

                try:
                    sql = f"INSERT INTO `{table}` (`index`,price) values (0,{price})"
                    print(sql)
                    cursor.execute(sql)
                    result = cursor._last_executed
                except Exception as e:
                    print(f"Error inserting value into Live Price column: {e}")
                else:
                    log.info(f"Inserted value into Live Price column: {result}")
                finally:
                    cursor.close()

def subscribeTicker(ws,ticker):
    try:
        ws.send(json.dumps({
            "type": "subscribe", 
            "symbol": f'{ticker}'
        }))
    except Exception as e:
        log.error(f"Error subscribing to Ticker {ticker}: {e}")
    else:
         log.info(f"Successfully Subscribed to {ticker}")

def unsubscribeTicker(ws,ticker):
    try:
        ws.send(json.dumps({
            "type": "unsubscribe", 
            "symbol": f'{ticker}'
        }))
    except Exception as e:
        log.error(f"Error unsubscribing from Ticker {ticker}: {e}")
    else:
         log.info(f"Successfully Unsubscribed to {ticker}")

def on_message(ws, message):
    global database
    global db_user
    global db_host
    global db_pass

    ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker = fetchTicker(ws, database, db_user, db_pass, db_host)

    if old_ticker is not None and ws is not None and old_ticker != ticker:
        unsubscribeTicker(ws, old_ticker)

    if ticker is not None and ws is not None and old_ticker != ticker:
        subscribeTicker(ws, ticker)

    res = json.loads(message)
    #print(f'WS Message is {message}')
    #print(res)
    if 'data' in res:
        data = res['data']
        if 'p' in data[0]:
            live = res['data'][0]['p']

            log.info(f'Latest Price is {live}')

            try:
                updateLatestPrice(database, db_user, db_pass, db_host, live)
            except Exception as e:
                log.error(e)

            try:
                buildCandleDataFrame(ticker, database, db_user, db_pass, db_host, timeframe, live)
            except Exception as e:
                log.error(e)
        else:
            log.error(f"Key 'p' not found not found in {data}")
    else:
        log.error(f"Key 'data' not found in {res}")

def on_error(ws, error):
    log.info(f"Websocket Error: {error}")

def on_close(ws):
    log.info("Websocket Connection was closed!\n")
    #log.info('Attempting reconnect in 10s...')
    #sleep(10)
    #startWebsocket()

def on_open(ws):
    log.info('Finnhub Websocket Connection Established')

    ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker = fetchTicker(ws, database, db_user, db_pass, db_host)

    subscribeTicker(ws,ticker)

def fetchAlpacaCredentials():
    global db_host
    global db_user
    global db_pass
    global database

    connection = pymysql.connect(host=db_host,
                         user=db_user,
                         password=db_pass,
                         database=database,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor,
                         autocommit=True)
    table = 'credentials'
    with connection.cursor() as cursor:

        if checkTableExists(table, cursor):
            try:
                sql = f"SELECT alpaca_key, alpaca_secret, FROM {table};"
                cursor.execute(sql)
                res = cursor.fetchone()
            except Exception as e:
                log.error(f"Error fetching Credentials: {e}")
            else:
                log.info(f"Credentials Response was {res}")

                if 'alpaca_key' in res and 'alpaca_secret' in res:
                    return res['alpaca_key'], res['alpaca_secret']
                else:
                    log.error("Credentials response was malformed!")

def sendTradeWebhook(ticker, data):
    alpaca_key, alpaca_secret = fetchAlpacaCredentials()

    if alpaca_key[0:2] == 'PK':
        api = tradeapi.REST(alpaca_key, alpaca_secret, 'https://paper-api.alpaca.markets')
        log.info('Using AlpacaPaper Trading API')
    elif alpaca_key[0:2] == 'AK':
        api = tradeapi.REST(alpaca_key, alpaca_secret, 'https://api.alpaca.markets')
        log.info('Using Alpaca Live Trading API')
    else:
        log.error(f'Error: API Key {alpaca_key} is malformed.')
        sendDiscordMessage(f'Error: API Key {alpaca_key} is malformed.')

    try:
        order = api.submit_order(
                    symbol=ticker,
                    qty=data['qty'],
                    side=data['side'],
                    type='limit',
                    limit_price=data['price'],
                    time_in_force='day',
                )
    except tradeapi.rest.APIError as e:
        log.error(e)
    else:
        log.info(order)
    #url = f"https://trading.battista.dev/?APCA_API_KEY_ID={APCA_API_KEY_ID}&APCA_API_SECRET_KEY={APCA_API_SECRET_KEY}"
    #res = requests.post(url, data)
    #log.info(res)

def sendDiscordMessage(message):
    url = "https://discord.com/api/webhooks/831890918796820510/OWR1HucrnJzHdTE-vASdf5EIbPC1axPikD4D5lh0VBn413nARUW4mla3xPjZHWCK9-9P"
    debug_url = "https://discord.com/api/webhooks/832603152330784819/yA1ZK7ymT3XBU0fJtg0cKZ9RNMPS0C9h0IDABmZZd_KIquToIODOSVOJ6k2aJQSrwC8I"
    webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    if message is None:
        log.warning('Error: Discord Message is empty!')
    else:
        webhook = Webhook.from_url(debug_url, adapter=RequestsWebhookAdapter())
        webhook.send(message)

def updateAvd(ticker, database, db_user, db_pass, db_host, value, timestamp):
    keys = ("value","timestamp")

    table = f"{ticker}-avd"

    connection = pymysql.connect(host=db_host,
                             user=db_user,
                             password=db_pass,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            try:
                sql = f"INSERT INTO `{table}` ({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}');"
                res = cursor.execute(sql)
                result = cursor._last_executed
            except Exception as e:
                log.error(f"Error updating AVD table: {e}")
            else:
                log.info(f"Successfully Updated AVD value: {result}")
                log.info(f"Rows Modified = {cursor.rowcount}")
            finally:
                cursor.close()
        else:
            try:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({keys[0]} DOUBLE,{keys[1]} DATETIME);"
                cursor.execute(sql)
                result = cursor._last_executed
            except Exception as e:
                log.error(f"Error creating AVD table: {e}")
            else:
                log.info(f"Successfully created AVD table: {result}")

                try:
                    sql = f"INSERT INTO `{table}`({keys[0]},{keys[1]}) values ({value},'{timestamp}')"
                    cursor.execute(sql)
                    result = cursor._last_executed
                except Exception as e:
                    log.error(f"Error inserting values into AVD table: {e}")
                else:
                    log.info(f"Successfully inserted values {value}, {timestamp} in AVD table")
                    log.info(f"Rows Modified = {cursor.rowcount}")
                finally:
                    cursor.close()
                    
#def fetchAvd(ticker, database, db_user, db_pass, db_host):
#    avd = {}
#    table = f"{ticker}-avd"
#    connection = pymysql.connect(host=db_host,
#                             user=db_user,
#                             password=db_pass,
#                             database=database,
#                             charset='utf8mb4',
#                             cursorclass=pymysql.cursors.DictCursor,
#                             autocommit=True)#

#    with connection.cursor() as cursor:
#        if checkTableExists(table, cursor):
#            log.info("Fetching AVD")
#            try:
#                sql = f"SELECT (value) FROM `{table}`"
#                print(sql)
#                cursor.execute(sql)
#                values = [item['value'] for item in cursor.fetchall()]
#            except Exception as e:
#                log.error(f"Fetch AVD Error: {e}")
#            else:
#                log.info(f"Fetched AVD values: {values}")
#                avd['values'] = values#

#            try:
#                sql = f"SELECT (timestamp) FROM `{table}`"
#                print(sql)
#                cursor.execute(sql)
#                timestamps = [item['timestamp'] for item in cursor.fetchall()]
#            except Exception as e:
#                log.error(f"Fetch AVD Error: {e}")
#            else:
#                log.info(f"Fetched AVD timestamps: {timestamps}")
#                avd['timestamps'] = timestamps#

#        log.info(avd)
#        cursor.close()#

#        return avd

def updateAvn(ticker, database, db_user, db_pass, db_host, value, timestamp):
    keys = ("value","timestamp")
    table = f"{ticker}-avn"
    connection = pymysql.connect(host=db_host,
                             user=db_user,
                             password=db_pass,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor) and avn is not None:
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

#def fetchAvn(ticker, database, db_user, db_pass, db_host):
#    avn = {}
#    key = "avn"
#    table = f"{ticker}-avn"
#    connection = pymysql.connect(host=DB_HOST,
#                             user='root',
#                             password=DB_PASS,
#                             database=database,
#                             charset='utf8mb4',
#                             cursorclass=pymysql.cursors.DictCursor,
#                             autocommit=True)#

#    with connection.cursor() as cursor:
#        if checkTableExists(table, cursor):
#            log.info("Fetching AVN")
#            try:
#                sql = f"SELECT (value) FROM `{table}`"
#                print(sql)
#                cursor.execute(sql)
#                values = [item['value'] for item in cursor.fetchall()]
#                log.info(f"Fetched: {values}")
#                avn['values'] = values
#            except Exception as e:
#                log.error(f"Fetch AVN Error: {e}")#

#            try:
#                sql = f"SELECT (timestamp) FROM `{table}`"
#                print(sql)
#                cursor.execute(sql)
#                timestamps = [item['timestamp'] for item in cursor.fetchall()]
#                log.info(f"Fetched: {timestamps}")
#                avn['timestamps'] = timestamps
#            except Exception as e:
#                log.error(f"Fetch AVN Error: {e}")
#        cursor.close()#

#        return avn

def updateTsl(ticker, database, db_user, db_pass, db_host, value, timestamp):

    keys = ("value","timestamp")
    table = f"{ticker}-tsl"
    connection = pymysql.connect(host=db_host,
                             user=db_user,
                             password=db_pass,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            try:
                sql = f"INSERT INTO `{table}` ({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}');"
                log.info(sql)
                res = cursor.execute(sql)
                result = cursor._last_executed
            except Exception as e:
                log.error(f"Error adding TSL value: {e}")
            else:
                log.info(f"Successfully added TSL value: {result}")
                log.info(f"Rows Modified = {cursor.rowcount}")
            finally:
                cursor.close()
        else:
            try:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({keys[0]} DOUBLE,{keys[1]} DATETIME);"
                log.info(sql)
                cursor.execute(sql)
                result = cursor._last_executed
            except Exception as e:
                print(f"Create TSL Error: {e}")
            else:
                log.info(f"Successfully created TSL table: {result}")

            try:
                sql = f"INSERT INTO `{table}`({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}')"
                cursor.execute(sql)
                result = cursor._last_executed
            except Exception as e:
                print(f"Error inserting TSL value: {e}")
            else:
                log.info(f"Successfully inserted TSL value: {result}")
                log.info(f"Rows Modified = {cursor.rowcount}")
            finally:
                cursor.close()

def executeTrade(ticker, live, side, use_inverse_trade):
    if use_inverse_trade:
        if ticker in inverse_table:

            inverse_ticker = inverse_table[ticker]

            log.info(f"Inverse Trade is true! Executing Inverse Trade with {ticker} and {inverse_ticker}.")

            data = {
              "ticker": ticker,
              "price": live,
              "qty": 100,
              "side": side,
              "inverse_ticker": inverse_ticker
            }
        else:
            log.info(f"There is no Inverse Ticker for Ticker {ticker}! Executing Normal Trade.")

            data = {
              "ticker": ticker,
              "price": live,
              "qty": 100,
              "side": side
            }
    else:
        log.info("Inverse Trade is false! Executing Normal Trade.")
        data = {
          "ticker": ticker,
          "price": live,
          "qty": 100,
          "side": side
        }

    log.info(data)
    sendDiscordMessage(data)
    sendTradeWebhook(ticker, data)

def checkBuySignal(live, use_inverse_trade):
    global buy_signal_flag
    global buy_signal_count
    global sell_signal_count
    global signal
    global signal_count_limit
    global inverse_table
    global inverse_trade

    if buy_signal_count > signal_count_limit and sell_signal_count == 0 and buy_signal_flag == False: 
        #Crossover of live price over tsl and higher than last candle close
        print(f'Crossover Buy is True')
        signal = 'Buy'
        sendDiscordMessage(f'Buy Signal Confirmed!')
        buy_signal_count = 0
        sell_signal_count = 0
        buy_signal_flag = True
        sell_signal_flag = False
        log.info(f"Live Price is {live}")

        executeTrade(data, live, 'buy', use_inverse_trade)

    elif buy_signal_flag == False:
        sell_signal_flag = False
        sendDiscordMessage(f'Recieved Buy signal with count {buy_signal_count}')
        buy_signal_count = buy_signal_count + 1
        buy_signal_flag = False
        
def checkSellSignal(live, use_inverse_trade):
    global sell_signal_flag
    global buy_signal_count
    global sell_signal_count
    global signal
    global signal_count_limit
    global inverse_table
    global inverse_trade
    global ticker

    if sell_signal_count > signal_count_limit and buy_signal_count == 0 and sell_signal_flag == False: 
        #Crossunder of live price under tsl and lower than last candle close
        print(f'Crossover Sell is True')
        signal = 'Sell'
        sendDiscordMessage(f'Sell Signal Confirmed!')
        sell_signal_count = 0
        buy_signal_count = 0
        sell_signal_flag = True
        buy_signal_flag = False

        executeTrade(data, live, 'sell', use_inverse_trade)

    elif sell_signal_flag == False :
        buy_signal_flag = False
        sendDiscordMessage(f'Recieved Sell signal with count {sell_signal_count}')
        log.info(buy_signal_count)
        log.info(sell_signal_flag)
        sell_signal_count = sell_signal_count + 1

def calculateSignal(ticker, database, db_user, db_pass, db_host, timeframe, fake_sensitivity, use_inverse_trade):
    global previous_avd
    global sup0
    global sup1
    global res0
    global res1
    global live
    global tsl
    global close
    global avn
    global avd
    global signal
    global signal_count
    global sell_signal_flag
    global buy_signal_flag

    sqlEngine = create_engine(f'mysql+pymysql://{db_user}:{db_pass}@{db_host}/{database}', pool_recycle=3600)

    dbConnection = sqlEngine.connect()

    try:
        data = fetchLastCandles(dbConnection)
    except Exception as e:
        log.error(e)
    else:
        if data is None:
            log.error(f"Error: Last Candle Data is {data}")
        else:
            table = f"{ticker}-live"
            signal_table = f"{ticker}-signal"

            connection = pymysql.connect(host=db_host,
                                     user=db_user,
                                     password=db_pass,
                                     database=database,
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor,
                                     autocommit=True)

            with connection.cursor() as cursor:
                log.info(checkTableExists(table, cursor))
                if checkTableExists(table, cursor):
                    try:
                        sql = f"SELECT * FROM `{table}`"
                        cursor.execute(sql)
                        res = cursor.fetchone()
                    except Exception as e:
                        raise(e)
                    else:
                        live = res['price']

                    log.info(f"Live Price is {live}")

                    if data is not None and live is not None:
                        now_utc = utc.localize(datetime.utcnow())
                        now_est = now_utc.astimezone(tz)
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

                        print(f"Sup0 is {sup0}")
                        print(f"Sup1 is {sup1}")
                        print(f"Res0 is {res0}")
                        print(f"Res1 is {res1}")

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
                            updateAvd(ticker, database, db_user, db_pass, db_host, avd, now_est)

                        # AVN  - AVD value of last non-zero condition stored.
                        if avd != 0:
                            avn = avd
                            updateAvn(ticker, database, db_user, db_pass, db_host, avn, now_est)
                        print(f'AVN is {avn}')

                        # TSL line
                        if avn == 1:
                            tsl = sup0
                        else:
                            tsl = res0

                        log.info(f'TSL is {tsl}')

                        if tsl is not None:
                            updateTsl(ticker, database, db_user, db_pass, db_host, tsl,now_est)

                        close = float(data.c.tail(1).iloc[0])

                        log.info(f"buy_signal_flag is {buy_signal_flag}")
                        log.info(f"sell_signal_flag is {sell_signal_flag}")
                        log.info(f"live is {live}")
                        log.info(f"tsl is {tsl}")
                        log.info(f"close is {close}")

                        if live > tsl and live > close and avn is not None:
                            log.info('Buy Signal!')
                            checkBuySignal(live, use_inverse_trade)

                        if live < tsl and live < close and avn is not None:
                            log.info('Sell Signal!')
                            checkSellSignal(live, use_inverse_trade)

                        if checkTableExists(signal_table, cursor):
                            try:
                                #sql = f"INSERT INTO `{signal_table}` (`index`,value) VALUES (0,{signal});"
                                sql = f"UPDATE `{signal_table}` SET value = '{signal}' WHERE `index` = 0"
                                res = cursor.execute(sql)
                                result = cursor._last_executed
                                log.info(f"Update: {result}")
                            except Exception as e:
                                log.error(f"Update Signal Table Error: {e}")
                            finally:
                                cursor.close()
                        else:
                            try:
                                sql = f"CREATE TABLE IF NOT EXISTS `{signal_table}` (`index` BIGINT,value TEXT);"
                                cursor.execute(sql)
                                result = cursor._last_executed
                                log.info(f"Create: {result}")
                            except Exception as e:
                                log.info(f"Create Signal Table Error: {e}")

                            try:
                                sql = f"INSERT INTO `{signal_table}` (`index`,value) VALUES (0,'{signal}')"
                                log.info(sql)
                                cursor.execute(sql)
                                result = cursor._last_executed
                                log.info(result)
                            except Exception as e:
                                log.info(f"Insert Signal Table Error: {e}")
                            finally:
                                cursor.close()
                else:
                    try:
                        sql = f"CREATE TABLE IF NOT EXISTS `{table}` (`index` BIGINT, price FLOAT);"
                        cursor.execute(sql)
                        result = cursor._last_executed
                    except Exception as e:
                        log.info(f"Error creating Live Table Error: {e}")
                    else:
                        log.info(f"Created Live Table: {result}")
    finally:
        dbConnection.close()

def fetchLastCandles(dbConnection):
    try:
        data = pd.read_sql_query(f"select * from `{ticker}`", dbConnection);
    except Exception as e:
        log.error(e)
    else:
        pd.set_option('display.expand_frame_repr', False)
        log.info(f"Fetched Table: {data}")

        return data
    finally:
        dbConnection.close()

def dropTables(ticker, database, db_user, db_pass, db_host):
    tables = ({ticker}, f"{ticker}-avn",f"{ticker}-avd",f"{ticker}-tsl",f"{ticker}-signal")

    connection = pymysql.connect(host=db_host,
                             user=db_user,
                             password=db_pass,
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
            except Exception as e:
                log.error(f"Error dropping Table {table}: {e}")
            else:
                log.info(f"Succesfully Dropped Table {table}: {result}")

        cursor.close()

def getTimeframe(cursor, ticker, diff):
    try:
        sql = f"SELECT COUNT(*) FROM `{ticker}`;"
        log.info(sql)
        cursor.execute(sql)
        count = cursor.fetchone()
    except Exception as e:
        log.error(e)
    else:
        log.info(count)

    try:
        sql = f"SELECT t FROM `{ticker}` where `index` = {count['COUNT(*)'] - diff};"
        print(sql)
        cursor.execute(sql)
        res = cursor.fetchone()
    except Exception as e:
        log.error(f"Error fetching Previous Timeframe: {e}")
    else:
        if res is not None and 't' in res:
            log.info(res['t'])
            return res['t']
        else:
            log.error(f"Res is malformed!")

#def fetchCurrentTimeframe(database, db_user, db_pass, db_host):#

#    table = 'ticker'#

#    connection = pymysql.connect(host=db_host,
#                             user=db_user,
#                             password=db_pass,
#                             database=database,
#                             charset='utf8mb4',
#                             cursorclass=pymysql.cursors.DictCursor,
#                             autocommit=True)#

#    with connection.cursor() as cursor:
#        if checkTableExists(table, cursor):
#            try:
#                sql = f"SELECT timeframe FROM {table};"
#                cursor.execute(sql)
#                res = cursor.fetchone()
#            except Exception as e:
#                log.error(f"Error fetching Timeframe: {e}")
#            else:
#                if res['timeframe'] is not None:
#                    timeframe = res['timeframe']
#            finally:
#                cursor.close()
#            log.info(f"Timeframe is {timeframe}")#

#            return timeframe
#        else:
#            log.error("Ticker table does not exists or is empty!")

def dropRows(ticker, cursor):
    try:
        sql = f"SELECT COUNT(*) FROM `{ticker}`"
        cursor.execute(sql)
        res = cursor.fetchone()
    except Exception as e:
        log.error(e)
    else:
        #log.info(f"Table Count is {count}")
        if res is not None and 'COUNT(*)' in res:
            while res['COUNT(*)'] > 6:
                try:
                    sql = f"DELETE FROM `{ticker}` ORDER BY `index` LIMIT 1]"
                    log.info(sql)
                    cursor.execute(sql)
                    res = cursor.fetchone()
                except Exception as e:
                    log.error(e)

def fetchHistoricalData(database, db_user, db_host, db_pass):
    ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker = fetchTicker(None, database, db_user, db_pass, db_host)

    sqlEngine = create_engine(f'mysql+pymysql://{db_user}:{db_pass}@{db_host}/{database}', pool_recycle=3600)

    connection = pymysql.connect(host=db_host,
                     user=db_user,
                     password=db_pass,
                     database=database,
                     charset='utf8mb4',
                     cursorclass=pymysql.cursors.DictCursor,
                     autocommit=True)

    log.info('Fetching Historical Data...')

    tz = timezone('US/Eastern')

    now = int(datetime.now(tz).timestamp())

    range = 5

    if timeframe == '1':
        log.info("Using 5m (5 x 1m intervals) difference")
        diff = range * 60 * 1 + 55
    elif timeframe == '5':
        log.info("Using 25m (5 x 5m interval) difference")
        diff = range * 60 * 5 + 55
    elif timeframe == '15':
        log.info("Using 75m (5 x 15m interval) difference")
        diff = range * 60 * 15 + 55
    elif timeframe == '30':
        log.info("Using 150m (5 x 30m intervals) difference")
        diff = range * 60 * 30 + 55
    elif timeframe == '60':
        log.info("Using 5 hour (5 x 1h interval) difference")
        diff = range * 60 * 60 + 55
    elif timeframe == 'D':
        log.info("Using 5 day (5 x 24h interval) difference")
        diff = range * 60 * 60 * 24 + 55

    log.info(f"Now is {now}")
    log.info(f"Diff is {diff}")
    then = now - diff
    log.info(f"Then is {then}")

    if ticker == 'BINANCE:BTCUSDT':
        url = f"https://finnhub.io/api/v1/crypto/candle?symbol={ticker}&resolution={timeframe}&from={then}&to={now}&token={finnhub_api_key}"
    else:
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={ticker}&resolution={timeframe}&from={then}&to={now}&token={finnhub_api_key}"

    print(url)
    log.info(f"Now: {datetime.fromtimestamp(now)}")

    log.info(f"Then: {datetime.fromtimestamp(then)}")

    res = requests.get(url)
    data = res.json()
    log.info(f"Historical JSON was {data}")

    if 's' in data and data['s'] == 'no_data':
        log.error(f"Finnhub JSON Response was {data}")
    elif 't' in data:
        timestamps = data['t']
        fmt = '%Y-%m-%d %H:%M:%S'

        for timestamp in timestamps:
            index = timestamps.index(timestamp)
            new_timestamp = datetime.fromtimestamp(timestamps[index]).astimezone(tz)
            timestamps[index] = new_timestamp.strftime(fmt)

        #print(data['t'])
        dataframe = pd.DataFrame.from_dict(data)

        #print(f"DataFrame is {dataframe}")

        index = len(dataframe.index)
        log.info(dataframe.at[index - 1,'t'])
        #date = datetime.now(tz)
        now_utc = utc.localize(datetime.utcnow())
        #print(now_utc)
        now_est = now_utc.astimezone(tz)

        with connection.cursor() as cursor:
            with sqlEngine.connect() as dbConnection:
                if checkTableExists(ticker, cursor):
                    dropRows(ticker, dbConnection)

                    #previous_time = datetime.strptime(getPreviousTimeframe(cursor, ticker), '%Y-%m-%d %H:%M:%S')
                    previous_time = getTimeframe(cursor, ticker, 2)
                    last_time = getTimeframe(cursor, ticker, 1)

                    log.info(f"Previous Timeframe is {previous_time}")

                    if previous_time is not None and hasattr(previous_time, 'minute'):
                        previous_minute = previous_time.minute

                    if last_time is not None and hasattr(last_time, 'minute'):
                        last_minute = last_time.minute

                    current_minute = now_est.minute

                    if timeframe is not None:
                        if timeframe == '1':
                            previous_timeframe = previous_time.minute
                            current_timeframe = now_est.minute
                            current_timeframe_string = now_est.strftime('%Y-%m-%d %H:%M:00')
                        elif timeframe == '5':
                            previous_timeframe = previous_time.minute
                            current_timeframe = now_est.minute
                            if current_minute.minute % 5 == 0:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:%M:00')
                            else:
                                minute = 5 * round(current_minute.minute/5)
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:{minute}:00')
                        elif timeframe == '15':
                            previous_timeframe = previous_time.day
                            current_timeframe = now_est.day
                            if current_minute.minute % 15 == 0:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:%M:00')
                            else:
                                minute = 15 * round(current_minute.minute/15)
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:{minute}:00')
                        elif timeframe == '30':
                            previous_timeframe = previous_time.minute
                            current_timeframe = now_est.minute
                            if current_minute.minute < 30:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:00:00')
                            else:
                                current_timeframe_string = now_est.strftime('%Y-%m-%d %H:30:00')
                        elif timeframe == '60':
                            previous_timeframe = previous_time.hour
                            current_timeframe = now_est.hour
                            current_timeframe_string = now_est.strftime('%Y-%m-%d %H:00:00')
                        elif timeframe == 'D':
                            previous_timeframe = previous_time.day
                            current_timeframe = now_est.day
                            current_timeframe_string = now_est.strftime('%Y-%m-%d 20:00:00')

                    log.info(f"Previous Minute is {previous_minute}")
                    log.info(f"Last Minute is {last_minute}")
                    log.info(f"Current minute {current_minute}")
                    log.info(f"Current Timefram String is {current_timeframe_string}")

                    if current_minute != previous_minute and current_minute != last_minute:
                        try:
                            cols = "`,`".join([str(i) for i in dataframe.columns.tolist()])
                            print(f"Dataframe Columns: {cols}")

                            # Insert DataFrame recrds one by one.
                            for i,row in dataframe.iterrows():

                                keys = ""

                                for k, v in zip(dataframe.columns.tolist(), tuple(row)):
                                    if k != "index":
                                        keys = keys + f"`{k}` = '{v}', "
                                keys = keys[:-2]

                                print(f"Keys/Values are {keys}")
                                i = i - 1

                                if i >= 0:
                                    try:
                                        #sql = f"UPDATE `{ticker}` SET {keys} WHERE `index` = {i}"
                                        sql = f"INSERT INTO `{ticker}` (`index`,c,h,l,o,s,t,v) VALUES ({i},{tuple(row)[0]},{tuple(row)[1]},{tuple(row)[2]},{tuple(row)[3]},'{tuple(row)[4]}','{tuple(row)[5]}',{tuple(row)[6]}) ON DUPLICATE KEY UPDATE {keys};"
                                        log.info(sql)
                                        cursor.execute(sql)
                                    except Exception as e:
                                        log.error(e)
                                    else:
                                        log.info(f"Rows Modified = {cursor.rowcount}")
                                        result = cursor._last_executed
                                        log.info(f"Sucessfully update table: {result}")
                                    
                        except ValueError as vx:
                            print(vx)
                        except Exception as ex:   
                            print(ex)
                        else:
                            print(f"Table {ticker} updated.");
                    else:
                        try:
                            cols = "`,`".join([str(i) for i in dataframe.columns.tolist()])
                            log.info(f"Dataframe Columns: {cols}")

                            # Insert DataFrame recrds one by one.
                            for i, row in dataframe.iterrows():

                                keys = ""

                                for k, v in zip(dataframe.columns.tolist(), tuple(row)):
                                    if k != "index":
                                        keys = keys + f"`{k}` = '{v}', "
                                keys = keys[:-2]

                                print(f"Keys/Values are {keys}")
                                
                                if i >= 0:
                                    try:
                                        #sql = f"UPDATE `{ticker}` SET {keys} WHERE `index` = {i}"
                                        sql = f"INSERT INTO `{ticker}` (`index`,c,h,l,o,s,t,v) VALUES ({i},{tuple(row)[0]},{tuple(row)[1]},{tuple(row)[2]},{tuple(row)[3]},'{tuple(row)[4]}','{tuple(row)[5]}',{tuple(row)[6]}) ON DUPLICATE KEY UPDATE {keys};"
                                        log.info(sql)
                                        cursor.execute(sql)
                                    except Exception as e:
                                        log.error(e)
                                    else:
                                        log.info(f"Rows Modified = {cursor.rowcount}")
                                        result = cursor._last_executed
                                        log.info(f"Sucessfully update table: {result}")
                                    
                        except ValueError as vx:
                            print(vx)
                        except Exception as ex:   
                            print(ex)
                        else:
                            print(f"Table {ticker} updated.");
                else:
                    log.info(f"Table {ticker} is empty or does not exist! Creating it now...")
                    try:
                        sql = f"DROP TABLE `{ticker}`;"
                        res = cursor.execute(sql)
                        result = cursor._last_executed
                    except Exception as e:
                        log.error(f"Error dropping Table {ticker}: {e}")
                    else:
                        log.info(f"Succesfully dropped Table {ticker}: {result}")

                    try:
                        sql = f"CREATE TABLE IF NOT EXISTS `{ticker}` (`index` BIGINT PRIMARY KEY, c DOUBLE, h DOUBLE, l DOUBLE, o DOUBLE, s TEXT, t DATETIME, v DOUBLE);"
                        cursor.execute(sql)
                        result = cursor._last_executed
                        log.info(f"Successfully created Table {ticker}: {result}")
                    except Exception as e:
                        log.error(f"Error creating Table {ticker}: {e}")

                    for i,row in dataframe.iterrows():
                            keys = ""
                            #print(f"index: {i}")
                            #print(f"Row: {row}")

                            for k, v in zip(dataframe.columns.tolist(), tuple(row)):
                                #print(k)
                                #print(v)
                                if k != "index":
                                    keys = keys + f"`{k}` = '{v}', "
                            keys = keys[:-2]

                            try:
                                sql = f"INSERT INTO `{ticker}` (`index`,c,h,l,o,s,t,v) VALUES ({i},{tuple(row)[0]},{tuple(row)[1]},{tuple(row)[2]},{tuple(row)[3]},'{tuple(row)[4]}','{tuple(row)[5]}',{tuple(row)[6]}) ON DUPLICATE KEY UPDATE {keys};"
                                cursor.execute(sql)
                                print(f"Rows Modified = {cursor.rowcount}")
                                result = cursor._last_executed
                                print(result)
                            except Exception as e:
                                print(f"Insert Error: {e}")
                try:
                    table = pd.read_sql(f"select * from `{ticker}`", dbConnection);
                except Exception as e:   
                    log.error(e)
                else:
                    log.info(f"Historical Table is {table}")
                finally:
                    cursor.close()
    else:
        log.error(f"Finnhub JSON Response was malformed: {data}")

def startWebsocket():
    global finnhub_api_key

    ws = websocket.WebSocketApp(f"wss://ws.finnhub.io?token={finnhub_api_key}",
                  on_open = on_open,
                  on_message = on_message,
                  on_error = on_error,
                  on_close = on_close)

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

def startHistorical():
    global database
    global db_user
    global db_host
    global db_pass

    ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker = fetchTicker(None, database, db_user, db_pass, db_host)

    dropTables(ticker, database, db_user, db_pass, db_host)

    fetchHistoricalData(database, db_user, db_host, db_pass)

    print("Scheduling Historical Fetch Job!")
    sched = BlockingScheduler()
    sched.add_job(fetchHistoricalData, 'cron', args=[database, db_user, db_host, db_pass], minute='0-59', second='5')
    sched.start()

def startCalculate():
    global database
    global db_user
    global db_host
    global db_pass

    ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker = fetchTicker(None, database, db_user, db_pass, db_host)

    sched = BlockingScheduler()
    sched.add_job(calculateSignal, 'interval', args=[ticker, database, db_user, db_pass, db_host, timeframe, fake_sensitivity, use_inverse_trade], seconds=5)
    sched.start()

def main():
    p0 = multiprocessing.Process(target=startHistorical)
    p1 = multiprocessing.Process(target=startWebsocket)
    p2 = multiprocessing.Process(target=startCalculate)
    
    p0.start()
    p1.start()
    p2.start()


if __name__ == '__main__':
    load_dotenv()

    db_pass = os.environ.get("DB_PASS")

    finnhub_api_key = os.environ.get("FINNHUB_API_KEY")

    db_host = os.environ.get("DB_HOST")

    if db_host is None:
        db_host = "127.0.0.1"

    if db_pass is None:
        log.error(f"db_pass is not set!")
    elif finnhub_api_key is None:
        log.error(f"finnhub_api_key is not set!")
    else:
        main()
