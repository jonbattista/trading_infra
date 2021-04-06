from flask import Flask, request
import requests
import os
import alpaca_trade_api as tradeapi
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from waitress import serve

import logging
from sys import stdout

# Define logger
logger = logging.getLogger('mylogger')

logger.setLevel(logging.DEBUG) # set logger level
logFormatter = logging.Formatter\
("%(name)-12s %(asctime)s %(levelname)-8s %(filename)s:%(funcName)s %(message)s")
consoleHandler = logging.StreamHandler(stdout) #set streamhandler to stdout
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

users_table = {
    'PK86UONPIG3S7CDKS0DD': 'Jon',
    #'': 'Jose',
    'PKSVMKPIHFFHFQMM61SU': 'Adam',
    'PK1BLDQH2VVZC7M5FNJB': 'Daniel'
}

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])


def alpaca():
    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')

    if APCA_API_KEY_ID in users_table:
        user = users_table[APCA_API_KEY_ID]
    else:
        user = APCA_API_KEY_ID

    print(f'User is {user}')
    data = request.data
    print(data)
    if(request.data):
        try:
            json_data = json.loads(data)
        except json.decoder.JSONDecodeError as e:
            print(f'Error parsing JSON: {e}')
            return f'Error parsing JSON: {e}', 500
        #print(json_data)
        #print(request.args)

        if request.args.get('APCA_API_KEY_ID') is None:
            return 'APCA_API_KEY_ID is not set!', 400
        if request.args.get('APCA_API_SECRET_KEY') is None:
            return 'APCA_API_SECRET_KEY is not set!', 400
        if json_data['ticker'] is None:
            return 'ticker is not set!', 400
        if json_data['price'] is None:
            return 'price is not set!', 400
        if json_data['side'] is None:
            return 'side is not set!', 400

        
        ticker = json_data['ticker']
        price = json_data['price']
        side = json_data['side']
        limit_price = float(price) * float('1.005')

        api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')

        account = api.get_account()

        buying_power = float(account.buying_power)
                
        print(f'Buying Power is {buying_power}')

        time_in_force_condition = 'time_in_force' not in json_data
        print(time_in_force_condition)
        if time_in_force_condition:
            time_in_force = 'day'
        else:
            time_in_force = json_data['time_in_force']

        order_type_condition = 'type' not in json_data
        print(order_type_condition)
        if order_type_condition:
            order_type = 'limit'
        else:
            order_type = json_data['order_type']

        if 'qty' not in json_data:
            qty = round(buying_power // limit_price)
        else:
            qty = json_data['qty']

        print(f'ticker is {ticker}')
        print(f'price is {price}')
        print(f'side is {side}')
        print(f'time_in_force is {time_in_force}')
        print(f'order_type is {order_type}')
        print(f'qty is {qty}')

        if account.trading_blocked:
            return 'Account is currently restricted from trading.', 400
        open_orders = api.list_orders()
        if not open_orders:
            print('No Open Orders found')
        else:
            print(f'{len(open_orders)} Open Orders were found!')

        if buying_power > 0:
            if qty > 0 and buying_power // qty > 0:
                try:
                    order = api.submit_order(
                        symbol=ticker,
                        qty=qty,
                        side=side,
                        type=order_type,
                        time_in_force=time_in_force,
                        limit_price=limit_price
                    )
                except alpaca_trade_api.rest.APIError as e:
                  print(e)
                  return f'{e}', 500
                print(order)
                if order.status == 'accepted':
                    print (f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')
                    return f'Success: Order to {side} of {qty} shares of {ticker}  at ${limit_price} was {order.status}', 200
                else:
                    print(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')
                    return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 200
            else:
                print(f'Error: User: {user} - Not enough Buying Power (${buying_power}) to buy {ticker} at limit price ${limit_price}')
                return f'Error: Not enough Buying Power (${buying_power}) to buy {ticker} at limit price ${limit_price}', 200
        print(f'Error: User: {user} - You have no Buying Power: ${buying_power}')
        return f'Error: You have no Buying Power: ${buying_power}', 200
    else:
        print(f'Error: User {user} - Data Payload was empty!')
        return f'Error: User {user} - Data Payload was empty!', 200 

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
