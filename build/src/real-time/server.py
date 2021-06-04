import websocket
import ssl
import json
import sched
from sqlalchemy import create_engine
import pymysql.cursors
import pandas as pd
from datetime import datetime
import time 
import logging
from sys import stdout
import pymysql.cursors
import os
from dotenv import load_dotenv
from pytz import timezone, utc
from time import sleep

load_dotenv()

DB_PASS = os.environ.get("DB_PASS")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")

DB_HOST = os.environ.get("DB_HOST")

if DB_HOST is None:
    DB_HOST = "127.0.0.1"

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
        count = cursor.fetchone()
    except Exception as e:
        count = None

    #log.info(f"Table Count is {count}")
    if count is not None and count['COUNT(*)'] > 0:
        return True
    else:
        return False

def buildCandleDataFrame(live):
    global ticker
    global DB_HOST
    global DB_PASS
    global timeframe

    sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@{DB_HOST}/{database}', pool_recycle=3600)
    connection = pymysql.connect(host=DB_HOST,
                         user='root',
                         password=DB_PASS,
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
                    raise(e)

                df_len = len(data.index) 
                #print(df_len)
                print(data)
                print(f"Dataframe Size is {df_len}")

                if len(data.index) > 0:

                    #while len(data.index) > 5:
                    #    data = data.drop(data.index[0])

                    print(data)
                    index = df_len - 1
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
                    #print(now_utc)
                    now_est = now_utc.astimezone(tz)
                    #print(now_est)

                    previous_time = data.at[index - 1,'t'].to_pydatetime()
                    print(previous_time)
                    previous_timeframe = None
                    current_timeframe = None
                    log.info(f"Timeframe is {timeframe}")
                    if timeframe is not None and timeframe:
                        if timeframe == '30m':
                            previous_timeframe = previous_time.minute
                            current_timeframe = now_est.minute
                        elif timeframe == '1h' or timeframe == '4h':
                            previous_timeframe = previous_time.hour
                            current_timeframe = now_est.hour
                    else:
                        log.error("Timeframe is not set!")

                    print(f"Previous Timeframe is {previous_timeframe}")
                    print(f"Current Timeframe is {current_timeframe}")

                    current_timeframe_string = now_est.strftime('%Y-%m-%d %H:%M:00')

#                    if current_minute > previous_minute:
#                        i = df_len
#                        #new_row = pd.DataFrame([(i, close_value, high_value, low_value, open_value, 'ok', current_minute_string, 0)], index=[i], columns=('index','c','h','l','o','s','t','v'))
#                        #print(new_row)
#                        #data = data.append(new_row)
#                        #print(data)
#                        #data = data.drop(data.index[0])
#                        #print(data)
#                        keys = f"`index`= {i}, `c` = {close_value}, `h` = {high_value}, `l` = {low_value}, `o` = {open_value}, `s` = 'ok', `t` = '{current_minute_string}', `v` = 0"
#                        try:
#                            sql = f"INSERT INTO `{ticker}` SET {keys}"
#                            print(sql)
#                            #print(tuple(row))
#                            cursor.execute(sql)
#                            print(f"Rows Modified = {cursor.rowcount}")
#                        except Exception as e:
#                            log.info(e)
#                    else:
                    data.at[index,'index']=index
                    data.at[index,'o']=open_value
                    data.at[index,'h']=high_value
                    data.at[index,'l']=low_value
                    data.at[index,'c']=close_value
                    data.at[index,'v']=0
                    data.at[index,'t']=current_timeframe_string

                    log.info(data)
                    cols = "`,`".join([str(i) for i in data.columns.tolist()])
                    #print(f"Columns: {cols}")

                    # Insert DataFrame recrds one by one.
                    for i,row in data.iterrows():
                        #print(f"index: {i}")
                        #print(f"Row: {row}")
                        #values = "`,`".join([str(i) for i in row])
                        #print(values)
                        keys = ""

                        for k, v in zip(data.columns.tolist(), tuple(row)):
                            #print(k)
                            #print(v)
                            if k != "index":
                                keys = keys + f"`{k}` = '{v}', "

                        keys = keys[:-2]

                        print(f"Keys {keys}")
                        try:
                            sql = f"UPDATE `{ticker}` SET {keys} WHERE `index` = {i}"
                            #print(sql)
                            #print(tuple(row))
                            cursor.execute(sql)
                            print(f"Rows Modified = {cursor.rowcount}")
                        except Exception as e:
                            log.info(e)
                    try:
                        new_table = pd.read_sql(f"SELECT * FROM `{ticker}`", dbConnection);
                    except Exception as e:
                        log.info(e)

                    pd.set_option('display.expand_frame_repr', False)
                    
                    log.info(f"Updated Table is {new_table}")
                    cursor.close()

                else:
                    log.info(f"Table {ticker} is empty")
                    cursor.close()
            else:
                log.info(f"Table {ticker} does not exist or is empty!")
                cursor.close()

def updateLatestPrice(price):
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    table = f"{ticker}-live"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
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
                log.info(f"Update: {result}")
            except Exception as e:
                log.error(f"Update Live Price Error: {e}")
            finally:
                cursor.close()
        else:
            try:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` (`index` INT PRIMARY KEY, price FLOAT);"
                print(sql)
                cursor.execute(sql)
                result = cursor._last_executed
                print(f"Create: {result}")
            except Exception as e:
                print(f"Create Live Price Error: {e}")

            try:
                sql = f"INSERT INTO `{table}` (`index`,price) values (0,{price})"
                print(sql)
                cursor.execute(sql)
                result = cursor._last_executed
                print(result)
            except Exception as e:
                print(f"Insert Live Price Error: {e}")
            finally:
                cursor.close()

def subscribeTicker(ws,ticker):
    try:
        ws.send(json.dumps({
            "type": "subscribe", 
            "symbol": f'{ticker}'
        }))
        log.info(f"Subscribed to {ticker}")
    except Exception as e:
        log.error(e)

def unsubscribeTicker(ws,ticker):
    try:
        ws.send(json.dumps({
            "type": "unsubscribe", 
            "symbol": f'{ticker}'
        }))
        log.info(f"Unsubscribed to {ticker}")
    except Exception as e:
        log.error(e)

def on_message(ws, message):
    global live_price
    global ticker

    fetchTicker(ws)

    res = json.loads(message)
    #print(f'WS Message is {message}')
    #print(res)
    if 'data' in res:
        live_price = res['data'][0]['p']
        print(f'Latest Price is {live_price}')
        #db.collection.find().sort({_id:-1})
        updateLatestPrice(live_price)
        try:
            buildCandleDataFrame(live_price)
        except Exception as e:
            log.error(e)


def on_error(ws, error):
    log.info(error)

def on_close(ws):
    log.info("Connection closed\n")
    sleep(10)
    log.info('Reconnecting...')
    startWebsocket()

def on_open(ws):
    global ticker

    log.info('Websocket Connection Established')

    fetchTicker(ws)

    subscribeTicker(ws,ticker)

def startWebsocket(ticker):
    ws = websocket.WebSocketApp(f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}",
                  on_open = on_open,
                  on_message = on_message,
                  on_error = on_error,
                  on_close = on_close)

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

def fetchTicker(ws):
    global ticker
    global database
    global DB_HOST
    global DB_PASS
    global timeframe

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
                sql = f"SELECT ticker, timeframe FROM {table};"
                cursor.execute(sql)
                res = cursor.fetchone()
            except Exception as e:
                log.error(f"Error fetching Ticker: {e}")
            else:
                log.info(f"Response is {res}")
                if ticker is None:
                    ticker = res['ticker']
                    log.info(f"Setting Ticker to {ticker}")
            
                if res['ticker'] is not None and old_ticker != res['ticker']:
                    ticker = res['ticker']
                    log.info(f"Updated Ticker from {old_ticker} to {ticker}")
                    log.info("Ticker changed. Updating Websocket...")
                    if old_ticker is not None:
                        unsubscribeTicker(ws, old_ticker)
                    if ticker is not None:
                        subscribeTicker(ws, ticker)
                if res['timeframe'] is not None:
                    timeframe = res['timeframe']
                print(f"Ticker is {ticker}")
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

def main():
    global ticker

    startWebsocket(ticker)

if __name__ == '__main__':
    if DB_PASS is not None or FINNHUB_API_KEY is not None:
        main()
    else:
        log.error(f"DB_PASS or FINNHUB_API_KEY is not set!")

