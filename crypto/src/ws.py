from twelvedata import TDClient
import asyncio
import websocket
import ssl
import json

td = TDClient(apikey="6ada7883b5494ec2ab023bbbf350a589")
ts = td.time_series(
    symbol="BTC/USD",
    outputsize=8,
    interval="1h",
)

ts.as_plotly_figure().show()


def appendToDataFrame(dataframe, dict):
    dataframe = dataframe.append(dict, ignore_index=True)

    return dataframe

def on_message(ws, message):
    print(message)

def on_error(ws, error):
    print(error)

def on_close(ws):
    print("Connection closed")

def on_open(ws):
    print('New connection established')

    ws.send(json.dumps({
      "action": "subscribe", 
      "params": {
        "symbols": "TQQQ"
      }
    }))

def run_connection(ws):
    try:
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    except Exception as e:
        print(f'Exception from websocket connection: {e}')
    finally:
        print("Trying to re-establish connection")
        time.sleep(3)
        run_connection(ws)

if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("wss://ws.twelvedata.com/v1/quotes/price?apikey=6ada7883b5494ec2ab023bbbf350a589",
                              on_open = on_open,
                              on_message = on_message,
                              on_error = on_error,
                              on_close = on_close)
    ws.run_forever()
    try:
        run_connection(ws)
    except Exception as e:
        print(e)
