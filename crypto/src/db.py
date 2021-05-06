import websocket
import config
import ssl
import json
from apscheduler.schedulers.blocking import BlockingScheduler
from twelvedata import TDClient
from sqlalchemy import create_engine
import pymysql
import pandas as pd

ticker = "TQQQ"

first_run = True

td = TDClient(apikey=config.API_KEY)

sqlEngine = create_engine(f'mysql+pymysql://root:@127.0.0.1/{ticker}', pool_recycle=3600)

dbConnection = sqlEngine.connect() 

def buildCandleDataFrame(live):
    global td
    global data
    global new_data
    global current_minute
    global last_minute
    global stock

    print(stock.index_information())


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

    todays_date = datetime.now()
    index = pd.date_range(todays_date, periods=1, freq='D')

    input = {'open':open_value, 'high':high_value,'low':low_value,'volume':0,'close':close_value}

    new_candle = pd.DataFrame(input, index=index)
    date = datetime.now()
    current_minute = date.strftime('%Y-%m-%d %H:%M:00.000000')

    print(f'Current Minute is {current_minute}')

    new_candle.index.values[0] = pd.Timestamp(current_minute)
    print(f'New Candle is {new_candle}')
    index_len = len(data.index.tolist())

    if index_len > 4 :
        stamp = data.index.tolist()
        index_stamp = stamp[len(stamp)-1]

        removed = data.drop(pd.Timestamp(index_stamp))
        new_data = removed.append(new_candle)
    else:
        new_data = data.append(new_candle)

def on_message(ws, message):
    global live_price
    res = json.loads(message)
    print(f'WS Message is {message}')
    if 'price' in res:
        live_price = res['price']
        print(f'Latest Price is {live_price}')
        #db.collection.find().sort({_id:-1})
        buildCandleDataFrame(live_price)

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

def fetchHistoricalData(td):
    global first_run
    global data
    global stock

    ts = td.time_series(
        symbol=ticker,
        outputsize=4,
        interval="1min",
        timezone="America/New_York",
        order='asc',
        prepost=True
    )
    data = ts.as_pandas()
    data.to_sql(tableName, dbConnection, if_exists='fail');

    try:
        frame  = dataFrame.to_sql(tableName, dbConnection, if_exists='fail');
    except ValueError as vx:
        print(vx)
    except Exception as ex:   
        print(ex)
    else:
        print("Table %s created successfully."%tableName);   

    frame = pd.read_sql(f"select * from stocks.{ticker}", dbConnection);

    pd.set_option('display.expand_frame_repr', False)
    
    print(frame)

    if first_run == True:
        first_run = False
        sched = BlockingScheduler()
        print('Adding Cron Job!')
        sched.add_job(fetchHistoricalData, 'cron', args=[td], minute='0-59', second='25')
        sched.start()

def main():
    global live_price
    global ticker
    global td
    fetchHistoricalData(td)
#    websocket.enableTrace(True)
#    ws = websocket.WebSocketApp(f"wss://ws.twelvedata.com/v1/quotes/price?apikey={config.API_KEY}",
#                          on_open = on_open,
#                          on_message = on_message,
#                          on_error = on_error,
#                          on_close = on_close)
#    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

if __name__ == '__main__':
    ticker = 'TQQQ'
    main()
