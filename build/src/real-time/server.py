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

load_dotenv()

DB_PASS = os.environ.get("DB_PASS")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")

ticker = "BINANCE:BTCUSDT"
database = "trades"

first_run = True

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.propagate = False
consoleHandler = logging.StreamHandler(stdout)
log.addHandler(consoleHandler)

def checkTables(table, cursor):
    try:
        sql = f"SELECT COUNT(*) FROM `{ticker}`"
        cursor.execute(sql)
        count = cursor.fetchone()
    except Exception as e:
        count = None     
    
    return count

def buildCandleDataFrame(live):
    global ticker

    sqlEngine = create_engine(f'mysql+pymysql://root:{DB_PASS}@127.0.0.1/{database}', pool_recycle=3600)
    connection = pymysql.connect(host='localhost',
                         user='root',
                         password=DB_PASS,
                         database=database,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor,
                         autocommit=True)

    with connection:
        with connection.cursor() as cursor:
            with sqlEngine.connect() as dbConnection:
                count = checkTables(ticker,cursor)
                print(count)
                if count is not None and count is True:
                    try:
                        data = pd.read_sql(f"SELECT * FROM `{ticker}`", dbConnection);
                    except Exception as e:
                        raise(e)

                    df_len = len(data.index)
                    print(df_len)
                    print(f"Dataframe Size is {df_len}")
                    if df_len > 0:
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

                        #todays_date = datetime.now()
                        #index = pd.date_range(todays_date, periods=1, freq='D')

                        #input = {'open':open_value, 'high':high_value,'low':low_value,'volume':0,'close':close_value}
                        data.at[index,'o']=open_value
                        data.at[index,'h']=high_value
                        data.at[index,'l']=low_value
                        data.at[index,'c']=close_value
                        data.at[index,'v']=0

                        #new_candle = pd.DataFrame(input, index=index)
                        #now = int(datetime.now().timestamp())
                        date = datetime.now()
                        current_minute = date.strftime('%Y-%m-%d %H:%M:00')
                        data.at[index,'t']=current_minute

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
                        cols = "`,`".join([str(i) for i in data.columns.tolist()])
                        print(f"Columns: {cols}")

                        # Insert DataFrame recrds one by one.
                        for i,row in data.iterrows():
                            print(f"index: {i}")
                            print(f"Row: {row}")
                            #values = "`,`".join([str(i) for i in row])
                            #print(values)
                            keys = ""
#                            i = 0
#                            while i < len(tuple(row)):
#                                v = tuple(row)[i]
#                                print(v)
#                                while i < len(data.columns.tolist()):
#                                    k = data.columns.tolist()[i]
#                                    keys = keys + f"{k}={v},"
#                                    i = i + 1
                            for k, v in zip(data.columns.tolist(), tuple(row)):
                                print(k)
                                print(v)
                                if k != "index":
                                    keys = keys + f"`{k}` = '{v}', "

                            keys = keys[:-2]

                            print(f"Keys {keys}")
                            try:
                                #sql = f"UPDATE INTO `{ticker}` (`" +cols + "`) VALUES (" + "%s,"*(len(row)-1) + "%s)"
                                sql = f"UPDATE `{ticker}` SET {keys} WHERE `index` = {i}"
                                print(sql)
                                print(tuple(row))
                                cursor.execute(sql)
                            except Exception as e:
                                print(e)

                    else:
                        log.info(f"Table {ticker} is empty")


                    try:
                        new_table = pd.read_sql(f"SELECT * FROM `{ticker}`", dbConnection);
                    except Exception as e:
                        print(e)

                    pd.set_option('display.expand_frame_repr', False)
                    
                    print(f"Updated Table is {new_table}")
                else:
                    log.info(f"Table {ticker} does not exist!")

def checkTables(table,cursor):
    stmt = f"SHOW TABLES LIKE '{table}'"
    cursor.execute(stmt)
    result = cursor.fetchone()
    print(result)
    if result:
        return True
    else:
        return False

def updateLatestPrice(price):
    global ticker
    global database

    table = f"{ticker}-live"
    connection = pymysql.connect(host='localhost',
                             user='root',
                             password=DB_PASS,
                             database=database,
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
    with connection:
        with connection.cursor() as cursor:
            if checkTables(table, cursor):
                try:
                    sql = f"INSERT INTO `{table}` (id,price) VALUES (1,{price}) ON DUPLICATE KEY UPDATE price={price};"
                    res = cursor.execute(sql)
                    result = cursor._last_executed
                    log.info(f"Update: {result}")
                except Exception as e:
                    log.error(f"Update Error: {e}")
                finally:
                    cursor.close()
            else:
                try:
                    sql = f"CREATE TABLE IF NOT EXISTS `{table}` (id INT PRIMARY KEY, price FLOAT);"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(f"Create: {result}")
                except Exception as e:
                    print(f"Create Error: {e}")

                try:
                    sql = f"INSERT INTO `{table}`(id,price) values (1,{price})"
                    cursor.execute(sql)
                    result = cursor._last_executed
                    print(result)
                except Exception as e:
                    print(f"Insert Error: {e}")
                finally:
                    cursor.close()


def on_message(ws, message):
    global live_price

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
    print(error)

def on_close(ws):
    print("Connection closed")

def on_open(ws):
    global ticker

    print('Websocket Connection Established')

    try:
        ws.send(json.dumps({
            "type": "subscribe", 
            "symbol": f'{ticker}'
        }))
    except Exception as e:
        print(e)

def main():
    global td

    ws = websocket.WebSocketApp(f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}",
                  on_open = on_open,
                  on_message = on_message,
                  on_error = on_error,
                  on_close = on_close)

    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == '__main__':
    main()
