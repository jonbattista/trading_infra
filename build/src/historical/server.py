import websocket
import ssl
import json
import sched
from twelvedata import TDClient
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

    sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@127.0.0.1/{database}', pool_recycle=3600)

    dbConnection = sqlEngine.connect()

    print('Fetching Historical Data...')
#    ts = td.time_series(
#        symbol=ticker,
#        outputsize=3,
#        interval="1min",
#        timezone="America/New_York",
#        order='asc'
#    )

#    data = ts.as_pandas()
#    print(f"Time Series is {data}")
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
        #sql = f"CREATE TABLE `{ticker}` (`index` BIGINT, c DOUBLE, h double, l double, o double, s text, t text, v double)"
        #cursor.execute(sql)
#    except Exception as e:
#        print(e)

#    print('meow')
#    cols = "`,`".join([str(i) for i in data.columns.tolist()])
#    print(f"Columns: {cols}")#

#    # Insert DataFrame recrds one by one.
#    for i,row in data.iterrows():
#        try:
#            sql = f"INSERT INTO `{ticker}` (`" +cols + "`) VALUES (" + "%s,"*(len(row)-1) + "%s)"
#            cursor.execute(sql, tuple(row))
#        except Exception as e:
#            print(e)

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
    
    #pd.set_option('display.expand_frame_repr', False)
    
    #print(f"Historical Table is {table}")

    

def main():
    print('Running Initial Historical Fetch!')

    fetchHistoricalData()

    print("Scheduling Fetch Loop!")
    sched = BlockingScheduler()
    sched.add_job(fetchHistoricalData, 'cron', args=[],  minute='0-59', second='1')
    sched.start()

if __name__ == '__main__':
    main()
