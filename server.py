from flask import Flask, request
import requests
import alpaca_trade_api as tradeapi
import json

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])

def alpaca():
    data = request.data

    print(data)
    print(json.loads(data))
    print(request.args)

    if request.args.get('APCA_API_KEY_ID') is None:
        return 'APCA_API_KEY_ID is not set!', 400

    if request.args.get('APCA_API_SECRET_KEY') is None:
        return 'APCA_API_SECRET_KEY is not set!', 400

    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')


    print(APCA_API_KEY_ID)
    print(APCA_API_SECRET_KEY)

    api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')

    account = api.get_account()

    if account.trading_blocked:
        return 'Account is currently restricted from trading.', 400

    #order = api.submit_order(SYMBOL, QUANTITY, TYPE, ORDER_TYPE, TIME_IN_FORCE)

    #print(order)
    #return f'Order was {order.status}'
    return 'got it', 200

if __name__ == '__main__':
  app.run(host='0.0.0.0', port=8080)
