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
import pymysql.cursors

ticker = "BTC/USD"
database = "trades"

first_run = True

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)

def buildCandleDataFrame(live):
    global ticker
    global dbConnection

    sqlEngine = create_engine(f'mysql+pymysql://root:{config.DB_PASS}@127.0.0.1/{database}', pool_recycle=3600)

    dbConnection = sqlEngine.connect()

    try:
        data = pd.read_sql(f"select * from `{ticker}`", dbConnection);
    except Exception as e:
        raise(e)

    df_len = len(data.index)
    print(f"Dataframe Size is {df_len}")
    index = df_len - 1
    open_value = round(data['open'].iloc[-1], 2)
    high_value = round(data['high'].iloc[-1], 2)
    low_value = round(data['low'].iloc[-1], 2)
    close_value = round(data['close'].iloc[-1], 2)

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

    #todays_date = datetime.now()
    #index = pd.date_range(todays_date, periods=1, freq='D')

    #input = {'open':open_value, 'high':high_value,'low':low_value,'volume':0,'close':close_value}
    data.at[index,'open']=open_value
    data.at[index,'high']=high_value
    data.at[index,'low']=low_value
    data.at[index,'close']=close_value
    data.at[index,'volume']=0

    #new_candle = pd.DataFrame(input, index=index)
    date = datetime.now()
    current_minute = date.strftime('%Y-%m-%d %H:%M:00')
    data.at[index,'datetime']=current_minute

    #print(f'Current Minute is {current_minute}')

    #new_candle.index.values[0] = pd.Timestamp(current_minute)
    #print(f'New Dataframe is {data}')
    #index_len = len(data.index.tolist())

    #if index_len > 4 :
        #stamp = data.index.tolist()
        #index_stamp = stamp[len(stamp)-1]

        #removed = data.drop(pd.Timestamp(index_stamp))
        #new_data = removed.append(new_candle)
        #print(new_data)
        #table  = new_data.to_sql(ticker, dbConnection, if_exists='replace');
    #else:
        #new_data = data.append(new_candle)
        #print(new_data)
    try:
        table = data.to_sql(ticker, dbConnection, index=False, if_exists='replace');
    except Exception as e:
        print(e)

    try:
        new_table = pd.read_sql(f"select * from `{ticker}`", dbConnection);
    except Exception as e:
        print(e)

    pd.set_option('display.expand_frame_repr', False)
    
    print(f"Updated Table is {new_table}")

    dbConnection.close()

def checkTables(table,cursor):
    stmt = "SHOW TABLES LIKE '%s' "% ('%'+str(table)+'%')
    cursor.execute(stmt)
    result = cursor.fetchone()
    print(result)   
    return result

def updateLatestPrice(price):
    global ticker
    global database

    table = f"{ticker}-live"
    connection = pymysql.connect(host='localhost',
                             user='root',
                             password=config.DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    connection.autocommit(True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                #sql = f"UPDATE `{table}`set price = {price}"
                sql = f"REPLACE INTO `{table}`(id,price) VALUES(1,{price});"
                cursor.execute(sql)
                result = cursor._last_executed
                print(result)
            else:
                sql = f"CREATE TABLE IF NOT EXISTS `{table}` (id INT AUTO_INCREMENT PRIMARY KEY, price INT) ENGINE = InnoDB;"
                cursor.execute(sql)
                result = cursor._last_executed
                print(result)
                sql = f"INSERT INTO `{table}`(price) values ({price})"
                cursor.execute(sql)
                result = cursor._last_executed
                print(result)

def on_message(ws, message):
    global live_price

    res = json.loads(message)
    #print(f'WS Message is {message}')
    if 'price' in res:
        live_price = res['price']
        print(f'Latest Price is {live_price}')
        #db.collection.find().sort({_id:-1})
        updateLatestPrice(live_price)
        try:
            buildCandleDataFrame(live_price)
        except Exception as e:
            print(e)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("Connection closed")

def on_open(ws):
    global ticker

    print('New connection established')

    ws.send(json.dumps({
      "action": "subscribe", 
      "params": {
        "symbols": f'{ticker}'
      }
    }))

def main():
    global td

    ws = websocket.WebSocketApp(f"wss://ws.twelvedata.com/v1/quotes/price?apikey={config.API_KEY}",
                  on_open = on_open,
                  on_message = on_message,
                  on_error = on_error,
                  on_close = on_close)

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == '__main__':
    main()
