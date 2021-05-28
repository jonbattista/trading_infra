import json
import time
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
from pytz import timezone
import pytz
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
from threading import Timer
from apscheduler.schedulers.blocking import BlockingScheduler
from time import sleep

load_dotenv()

DB_PASS = os.environ.get("DB_PASS")
DB_HOST = os.environ.get("DB_HOST")

if DB_HOST is None:
    DB_HOST = "127.0.0.1"

tz = timezone('US/Eastern')
now = datetime.now(tz)

ticker = None
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
signal_count_limit = 10



log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)

VALID_USERNAME_PASSWORD_PAIRS = {
    'lionheart': 'cleanandjerks'
}

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
    global DB_HOST
    global first_run
    global DB_PASS

    if first_run:
        first_run = False
        tables = (f"{ticker}-avn",f"{ticker}-avd",f"{ticker}-tsl",f"{ticker}-signal")
        print(tables)
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
                    log.error(f"Drop Table Error: {e}")
    
            cursor.close()

def fetchTicker():
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    old_ticker = ticker

    print(f"old_ticker is {old_ticker}")
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
            log.info(res)

            if ticker is None:
                ticker = res['ticker']
                log.info(f"Set Ticker to {ticker}")
            
            if res['ticker'] is not None and old_ticker != res['ticker']:
                ticker = res['ticker']
                log.info(f"Updated Ticker from {old_ticker} to {ticker}")
            print(f"Ticker is {ticker}")
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

def updateAvd(value,timestamp):
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    kind = "avd"

    keys = ("value","timestamp")
    table = f"{ticker}-{kind}"
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
    global DB_HOST
    global DB_PASS

    kind = "avn"

    keys = ("value","timestamp")
    table = f"{ticker}-{kind}"
    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
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
        cursor.close()

        return avn

def updateTsl(value,timestamp):
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    kind = "tsl"
    keys = ("value","timestamp")
    table = f"{ticker}-{kind}"
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
                print(keys)
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` ({keys[0]} DOUBLE,{keys[1]} DATETIME);"
                cursor.execute(sql)
                result = cursor._last_executed
                print(f"Create: {result}")
            except Exception as e:
                print(f"Create TSL Error: {e}")

            try:
                sql = f"INSERT INTO `{table}`({keys[0]},{keys[1]}) VALUES ({value},'{timestamp}')"
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

def checkBuySignal():
    global buy_signal_flag
    global buy_signal_count
    global sell_signal_count
    global signal
    global signal_count_limit

    if buy_signal_count > signal_count_limit and sell_signal_count == 0 and buy_signal_flag == False: 
        #Crossover of live price over tsl and higher than last candle close
        print(f'Crossover Buy is True')
        signal = 'Buy'
        sendDiscordMessage(f'Confirmed Buy signal!')
        buy_signal_count = 0
        sell_signal_count = 0
        buy_signal_flag = True
    else:
        sell_signal_flag = False
        #sendDiscordMessage(f'Recieved Buy signal with count {buy_signal_count}')
        buy_signal_count = buy_signal_count + 1
        
def checkSellSignal():
    global sell_signal_flag
    global buy_signal_count
    global sell_signal_count
    global signal
    global signal_count_limit

    if sell_signal_count > signal_count_limit and buy_signal_count == 0 and sell_signal_flag == False: 
        #Crossunder of live price under tsl and lower than last candle close
        print(f'Crossover Sell is True')
        signal = 'Sell'
        sendDiscordMessage(f'Confirmed Sell signal!')
        sell_signal_count = 0
        buy_signal_count = 0
        sell_signal_flag = True
    else:
        buy_signal_flag = False
        #sendDiscordMessage(f'Recieved Sell signal with count {sell_signal_count}')
        log.info(buy_signal_count)
        log.info(sell_signal_flag)
        sell_signal_count = sell_signal_count + 1

def calcTsl(data):
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
    global DB_HOST
    global DB_PASS
    global database
    global signal_count
    global sell_signal_flag
    global buy_signal_flag

    table = f"{ticker}-live"
    signal_table = f"{ticker}-signal"

    connection = pymysql.connect(host=DB_HOST,
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

    connection.autocommit(True)

    with connection.cursor() as cursor:
        if checkTableExists(table, cursor):
            try:
                sql = f"SELECT * FROM `{table}`"
                cursor.execute(sql)
                res = cursor.fetchone()
                live = res['price']
            except Exception as e:
                raise(e)

            log.info(live)
            if data is not None and live is not None:
                print(f'Live Price is {live}')
                print(f'TSL New Data is {data}')
                now_utc = pytz.utc.localize(datetime.utcnow())
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

                close = float(data.c.tail(1).iloc[0])

                if live > tsl and live > close and buy_signal_flag == False:
                    checkBuySignal()

                if live < tsl and live < close and sell_signal_flag == False:
                    checkSellSignal()

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
                        print(f"Create: {result}")
                    except Exception as e:
                        print(f"Create Signal Table Error: {e}")

                    try:
                        sql = f"INSERT INTO `{signal_table}` (`index`,value) VALUES (0,'{signal}')"
                        print(sql)
                        cursor.execute(sql)
                        result = cursor._last_executed
                        print(result)
                    except Exception as e:
                        print(f"Insert Signal Table Error: {e}")
                    finally:
                        cursor.close()
        else:
            try:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` (`index` BIGINT, price FLOAT);"
                cursor.execute(sql)
                result = cursor._last_executed
                print(f"Created: {result}")
            except Exception as e:
                print(f"Create Live Table Error: {e}")

def fetchLastCandles(dbConnection):
    try:
        data = pd.read_sql_query(f"select * from `{ticker}`", dbConnection);
    except Exception as e:
        raise(e)
    finally:
        dbConnection.close()

    pd.set_option('display.expand_frame_repr', False)
    print(f"Fetched Table: {data}")

    return data

def updateValues():
    global database
    global DB_HOST
    global DB_PASS

    fetchTicker()

    try:
        sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@{DB_HOST}/{database}', pool_recycle=3600)
    except Exception as e:
        raise(f"SQL Engine Error: {e}")

    dbConnection = sqlEngine.connect()

    new_data = fetchLastCandles(dbConnection)
        
    if new_data is not None:
        calcTsl(new_data)

def main():
    fetchTicker()
    dropTables()
    sched = BlockingScheduler()
    sched.add_job(updateValues, 'interval', seconds=3)
    sched.start()

if __name__ == '__main__':
    if DB_PASS is not None or FINNHUB_API_KEY is not None:
        main()
    else:
        log.error(f"DB_PASS is not set!")

