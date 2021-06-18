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

db_user = 'lionheart'
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
        cursor.close()
        log.info(f"Response is {res}")
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
                             cursorclass=pymysql.cursors.DictCursor,
                             connect_timeout=50,
                             autocommit=True)
    crs = connection.cursor()

    if checkTableExists(table, crs):
        with connection.cursor() as cursor:
            try:
                sql = f"SELECT ticker, timeframe, fake_sensitivity FROM `{table}`"
                cursor.execute(sql)
                res = cursor.fetchone()
            except Exception as e:
                log.error(f"Error fetching Ticker: {e}")
            else:
                timeframe = None
                log.info(f"Trade Parameters are {res}")

                if ticker is None and res['ticker']:
                    ticker = res['ticker']
                    log.info(f"Setting Ticker to {ticker}")
            
                if 'ticker' in res and res['ticker'] is not None and old_ticker != res['ticker']:
                    ticker = res['ticker']
                    log.info(f"Updated Ticker from {old_ticker} to {ticker}")

                if 'timeframe' in res and res['timeframe'] is not None:
                    timeframe = res['timeframe']
                    log.info(f"Timeframe is {timeframe}")

                if 'fake_sensitivity' in res and res['fake_sensitivity'] is not None:
                    fake_sensitivity = res['fake_sensitivity']
                    log.info(f"Fake Sensitivity is {fake_sensitivity}")

                if 'inverse_trade' in res and res['inverse_trade'] == 1:
                    use_inverse_trade = True
                else:
                    use_inverse_trade = False

                log.info(f"Use Inverse Trade is {use_inverse_trade}")

            if ticker is not None and timeframe is not None and fake_sensitivity is not None and use_inverse_trade is not None and old_ticker is not None:
                return ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker
            
    else:
        with connection.cursor() as cursor:
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
        
def main():
    global database
    global db_user
    global db_host
    global db_pass

    ticker, timeframe, fake_sensitivity, use_inverse_trade, old_ticker = fetchTicker(None, database, db_user, db_pass, db_host)

if __name__ == '__main__':
    load_dotenv()

    db_pass = os.environ.get("MYSQL_PASSWORD")

    finnhub_api_key = os.environ.get("FINNHUB_API_KEY")

    db_host = 'mysql'

    if db_pass is None:
        log.error(f"db_pass is not set!")
    elif finnhub_api_key is None:
        log.error(f"finnhub_api_key is not set!")
    else:
        sleep(5)
        main()
