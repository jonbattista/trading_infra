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

load_dotenv()

DB_PASS = os.environ.get("DB_PASS")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")

DB_HOST = os.environ.get("DB_HOST")

if DB_HOST is None:
    DB_HOST = "127.0.0.1"

ticker = None
database = "trades"
first_run = True

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)


def dropTables():
    global ticker
    global database
    global DB_HOST
    global first_run
    global DB_PASS

    if first_run:
        first_run = False
        tables = ({ticker}, f"{ticker}-avn",f"{ticker}-avd",f"{ticker}-tsl",f"{ticker}-signal")
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

def getPreviousTimeframe(cursor, ticker,):
    try:
        sql = f"SELECT COUNT(*) FROM `{ticker}`;"
        print(sql)
        cursor.execute(sql)
        count = cursor.fetchone()
    except Exception as e:
        print(e)
    print(count)
    try:
        sql = f"SELECT t FROM `{ticker}` where `index` = {count['COUNT(*)'] - 2};"
        print(sql)
        cursor.execute(sql)
        res = cursor.fetchone()
    except Exception as e:
        log.error(f"Error fetching Previous Timeframe: {e}")
    print(res['t'])
    return res['t']

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

def fetchHistoricalData():
    global ticker
    global database
    global DB_HOST
    global DB_PASS

    fetchTicker()

    sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@{DB_HOST}/{database}', pool_recycle=3600)

    connection = pymysql.connect(host=DB_HOST,
                     user='root',
                     password=DB_PASS,
                     database=database,
                     charset='utf8mb4',
                     cursorclass=pymysql.cursors.DictCursor,
                     autocommit=True)

    print('Fetching Historical Data...')

    timeframe = 1
    tz = timezone('US/Eastern')
    now = int(datetime.now(tz).timestamp())
    #print(now)
    range = 5
    diff = range * 60 * 1 + 55
    #print(diff)
    then = now - diff
    #print(then)

    if ticker == 'BINANCE:BTCUSDT':
        url = f"https://finnhub.io/api/v1/crypto/candle?symbol={ticker}&resolution={timeframe}&from={then}&to={now}&token={FINNHUB_API_KEY}"
    else:
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={ticker}&resolution={timeframe}&from={then}&to={now}&token={FINNHUB_API_KEY}"

    print(url)
    print(f"Now: {datetime.fromtimestamp(now)}")

    print(f"Then: {datetime.fromtimestamp(then)}")

    res = requests.get(url)
    data = res.json()
    #log.info(f"Data is {data}")

    if 's' in data and data['s'] == 'no_data':
        log.error(f"JSON Response was {data}")
    elif 't' in data:
        timestamps = data['t']
        fmt = '%Y-%m-%d %H:%M:%S'

        for timestamp in timestamps:
            index = timestamps.index(timestamp)
            new_timestamp = datetime.fromtimestamp(timestamps[index]).astimezone(tz)
            timestamps[index] = new_timestamp.strftime(fmt)

        #print(data['t'])
        df = pd.DataFrame.from_dict(data)

        print(f"DataFrame is {df}")

        index = len(df.index)
        print(df.at[index - 1,'t'])
        #date = datetime.now(tz)
        now_utc = utc.localize(datetime.utcnow())
        #print(now_utc)
        now_est = now_utc.astimezone(tz)

        with connection.cursor() as cursor:
            with sqlEngine.connect() as dbConnection:
                if checkTableExists(ticker, cursor):
                    #previous_time = datetime.strptime(getPreviousTimeframe(cursor, ticker), '%Y-%m-%d %H:%M:%S')
                    previous_time = getPreviousTimeframe(cursor, ticker)
                    print(previous_time)
                    previous_minute = previous_time.minute
                    current_minute = now_est.minute

                    print(f"Previous Minute is {previous_minute}")
                    print(f"Current minute {current_minute}")

                    current_minute_string = now_est.strftime('%Y-%m-%d %H:%M:00')
                    try:
                        cols = "`,`".join([str(i) for i in df.columns.tolist()])
                        print(f"Columns: {cols}")

                        if current_minute > previous_minute:
                            # Insert DataFrame recrds one by one.
                            for i,row in df.iterrows():
                                keys = ""
                                #print(f"index: {i}")
                                #print(f"Row: {row}")

                                for k, v in zip(df.columns.tolist(), tuple(row)):
                                    #print(k)
                                    #print(v)
                                    if k != "index":
                                        keys = keys + f"`{k}` = '{v}', "
                                keys = keys[:-2]

                                print(f"Keys/Values are {keys}")

                                try:
                                    sql = f"UPDATE `{ticker}` SET {keys} WHERE `index` = {i}"
                                    print(sql)
                                    cursor.execute(sql)
                                    print(f"Rows Modified = {cursor.rowcount}")
                                    result = cursor._last_executed
                                    #print(result)
                                except Exception as e:
                                    print(e)
                                try:
                                    new_table = pd.read_sql(f"SELECT * FROM `{ticker}`", dbConnection);
                                except Exception as e:
                                    print(e)

                                pd.set_option('display.expand_frame_repr', False)
                                
                    except ValueError as vx:
                        print(vx)
                    except Exception as ex:   
                        print(ex)
                    else:
                        print(f"Table {ticker} updated.");
                else:
                    try:
                        sql = f"CREATE TABLE IF NOT EXISTS `{ticker}` (`index` BIGINT PRIMARY KEY, c DOUBLE, h DOUBLE, l DOUBLE, o DOUBLE, s TEXT, t DATETIME, v DOUBLE);"
                        cursor.execute(sql)
                        result = cursor._last_executed
                        print(f"Create: {result}")
                    except Exception as e:
                        print(f"Create Error: {e}")

                    for i,row in df.iterrows():
                            keys = ""
                            #print(f"index: {i}")
                            #print(f"Row: {row}")

                            for k, v in zip(df.columns.tolist(), tuple(row)):
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
                except Exception as ex:   
                    print(ex)
                    fetchHistoricalData()
                else:
                    print(f"Historical Table is {table}")
                finally:
                    cursor.close()
    else:
        log.error(f"JSON Response was malformed: {data}")

def main():
    print('Running Initial Historical Fetch!')
    dropTables()
    fetchHistoricalData()

    print("Scheduling Fetch Loop!")
    sched = BlockingScheduler()
    sched.add_job(fetchHistoricalData, 'cron', args=[],  minute='0-59', second='*/5')
    sched.start()

if __name__ == '__main__':
    if DB_PASS is not None or FINNHUB_API_KEY is not None:
        main()
    else:
        log.error(f"DB_PASS or FINNHUB_API_KEY is not set!")
