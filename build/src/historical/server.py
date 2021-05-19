import websocket
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

load_dotenv()

DB_PASS = os.environ.get("DB_PASS")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")

#host = "mysql-server.default.svc.cluster.local"
host = "127.0.0.1"

ticker = "BINANCE:BTCUSDT"
database = "trades"

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)


def fetchHistoricalData():
    global ticker
    global database
    global host

    sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@{host}/{database}', pool_recycle=3600)

    dbConnection = sqlEngine.connect()

    print('Fetching Historical Data...')

    timeframe = 1
    now = int(datetime.now().timestamp())
    #print(now)
    range = 5
    diff = range * 60
    #print(diff)
    then = now - diff
    #print(then)

    url = f"https://finnhub.io/api/v1/crypto/candle?symbol={ticker}&resolution={timeframe}&from={then}&to={now}&token={FINNHUB_API_KEY}"

    print(f"Now: {datetime.fromtimestamp(now)}")

    print(f"Then: {datetime.fromtimestamp(then)}")

    res = requests.get(url)
    data = res.json()
    timestamps = data['t']

    print(timestamps)
    for timestamp in timestamps:
        index = timestamps.index(timestamp)
        timestamps[index] = datetime.fromtimestamp(timestamps[index])

    print(data['t'])
    df = pd.DataFrame.from_dict(data)

    print(df)

    try:
        table  = df.to_sql(ticker, dbConnection, index=True, if_exists='replace');

    except ValueError as vx:
        print(vx)
    except Exception as ex:   
        print(ex)
    else:
        print(f"Table {ticker} updated.");
        dbConnection.close()

    dbConnection = sqlEngine.connect()
    try:
        table = pd.read_sql(f"select * from `{ticker}`", dbConnection);
    except Exception as ex:   
        print(ex)
        fetchHistoricalData()
    else:
        print(f"Historical Table is {table}")
        dbConnection.close()

def main():
    print('Running Initial Historical Fetch!')

    fetchHistoricalData()

    print("Scheduling Fetch Loop!")
    sched = BlockingScheduler()
    sched.add_job(fetchHistoricalData, 'cron', args=[],  minute='0-59', second='1')
    sched.start()

if __name__ == '__main__':
    main()
