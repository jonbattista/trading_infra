import websocket
import config
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
from apscheduler.schedulers.blocking import BlockingScheduler

ticker = "BTC/USD"
database = "trades"

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)


def fetchHistoricalData(td):
    global ticker
    global database

#    mydb = mysql.connector.connect(
#      host="localhost",
#      user="root",
#      password=config.DB_PASS,
#      database=database
#    )#

#    mycursor = mydb.cursor()

#    mycursor.execute(f"SELECT * FROM {ticker}")

    sqlEngine = create_engine(f'mysql+pymysql://root:{config.DB_PASS}@127.0.0.1/{database}', pool_recycle=3600)

    dbConnection = sqlEngine.connect()

    print('Fetching Historical Data...')
    ts = td.time_series(
        symbol=ticker,
        outputsize=10,
        interval="5min",
        timezone="America/New_York",
        order='asc'
    )

    data = ts.as_pandas()
    print(f"Time Series is {data}")

    try:
        table  = data.to_sql(ticker, dbConnection, index=True, if_exists='replace');
    except ValueError as vx:
        print(vx)
    except Exception as ex:   
        print(ex)
    else:
        print(f"Table {ticker} updated.");

    try:
        table = pd.read_sql(f"select * from `{ticker}`", dbConnection);
    except Exception as ex:   
        print(ex)
        fetchHistoricalData(td)
    else:
        print(f"Historical Table is {table}")
        dbConnection.close()
    
    #pd.set_option('display.expand_frame_repr', False)
    
    #print(f"Historical Table is {table}")

    

def main():
    td = TDClient(apikey=config.API_KEY)

    print('Running Initial Historical Fetch!')

    fetchHistoricalData(td)

    print("Scheduling Fetch Loop!")
    sched = BlockingScheduler()
    sched.add_job(fetchHistoricalData, 'cron', args=[td],  minute='0-59', second='25')
    sched.start()

if __name__ == '__main__':
    main()
