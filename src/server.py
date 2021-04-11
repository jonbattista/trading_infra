from flask import Flask, request
import requests
import os
import alpaca_trade_api as tradeapi
import json
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from waitress import serve
import uuid
import logging
from sys import stdout
import math

# Configure Logging for Docker container
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)
logFormatter = logging.Formatter("%(name)-12s %(asctime)s %(levelname)-8s %(filename)s:%(funcName)s %(message)s")
consoleHandler = logging.StreamHandler(stdout)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

app = Flask(__name__)

app.debug = True

@app.route('/', methods=["POST"])

def alpaca():
    APCA_API_KEY_ID = request.args.get('APCA_API_KEY_ID')
    APCA_API_SECRET_KEY = request.args.get('APCA_API_SECRET_KEY')

    user = APCA_API_KEY_ID

    print(f'\n\nOrder received for User: {user}')
    data = request.get_data()

    #print(f'Data: {data}')

    if(request.data):
        try:
            json_data = json.loads(data)
        except json.decoder.JSONDecodeError as e:
            print(f'Error parsing JSON: {e}')
            return f'Error parsing JSON: {e}', 400

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
        if side == 'buy':
             # Set Buy Limit Price higher by 0.005% to ensure it gets filled
            limit_price = round(float(price) * float('1.005'),2)
            diff = round(abs(limit_price - price),2)
            print(f'Buying Limit Price is: ${price} + ${diff} = ${limit_price}')
        elif side == 'sell':
            # Set Sell Limit Price lower by 0.005% to ensure it gets filled
            limit_price = round(abs(float(price) * float('.995')),2)
            diff = round(abs(limit_price - price),2)
            print(f'Selling Limit Price is: ${price} - ${diff} = ${limit_price}')

        # Check if Live or Paper Trading
        if APCA_API_KEY_ID[0:2] == 'PK':
            api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://paper-api.alpaca.markets')
            #wss = tradeapi.stream2.StreamConn(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'wss://paper-api.alpaca.markets/stream')
            print('Using Paper Trading API')
        elif APCA_API_KEY_ID[0:2] == 'AK':
            api = tradeapi.REST(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'https://api.alpaca.markets')
            #wss = tradeapi.stream2.StreamConn(APCA_API_KEY_ID, APCA_API_SECRET_KEY, 'wss://api.alpaca.markets/stream')
            print('Using Live Trading API')
        else:
            return 'Error: API Key is malformed.', 400

        # Get Account information
        account = api.get_account()

        # Get available Buying Power
        buying_power = float(account.buying_power)       
        print(f'Buying Power is ${buying_power}')

        # Get Time-In-Force
        time_in_force_condition = 'time_in_force' not in json_data
        if time_in_force_condition:
            time_in_force = 'day'
        else:
            time_in_force = json_data['time_in_force']

        # Get Order Type
        order_type_condition = 'type' not in json_data
        if order_type_condition:
            order_type = 'limit'
        else:
            order_type = json_data['order_type']

        # Get Quantity
        if 'qty' not in json_data:
            qty = math.floor(buying_power // limit_price)
        else:
            qty = json_data['qty']

        # Get Stop Loss
        if 'stop' not in json_data:
            stop = None
            print('Not using a Stop Loss!')
        else:
            stop = float(json_data['stop'])
            print(f'Stop Loss is {stop}')

        # Prin Variables
        print(f'Ticker is {ticker}')
        print(f'Original Price is {price}')
        print(f'Side is {side}')
        print(f'Time-In-Force is {time_in_force}')
        print(f'Order Type is {order_type}')
        print(f'Quantity is {qty}')

        # Check if Account is Blocked
        if account.trading_blocked:
            return 'Account is currently restricted from trading.', 400
        open_orders = api.list_orders()

        # Check if there are any open orders
        if not open_orders:
            print('No Open Orders found')
        else:
            print(f'{len(open_orders)} Open Orders were found!')

        # Generate Order ID
        order_id = str(uuid.uuid4())

        # Get Positions
        portfolio = api.list_positions()
        if not portfolio:
            print('No Positions were found!')
        else:
            print(f'{len(portfolio)} Positions were found!')

        position = next((position for position in portfolio if position.symbol == ticker), None)
        open_orders = api.list_orders(
            status='open',
            limit=10,
        )
        # Check if there is already a Position for Ticker
        if position is not None and side == 'buy':
            print(f'Error: User: {user} - You already have a Position of {position.qty} shares in {ticker}')
            return f'Error: You already have a Position of {position.qty} in {ticker} shares', 400
        elif position is None and side == 'buy':
            print(f'No position for {ticker} found. Proceeding...')
        # Check if you are trying to sell something you dont have
        elif position is None and side == 'sell':
            print(f'Error: You have no  position in {ticker} to Sell. Aborting.')
            return f'Error: You have no position in {ticker} to Sell.', 400
        elif position is not None and side == 'sell':
            print(f'You have {position.qty} shares of {ticker} to Sell')

        open_order_qty = 0
        open_order_ticker_count = 0
        for open_order in open_orders:
            if  open_order.symbol == ticker:
                open_order_qty += int(open_order.qty)
                open_order_ticker_count += 1

        #open_order = next((open_order for open_order in open_orders if open_order.symbol == ticker), None)
        print(f'There are {open_order_qty} Open Orders for {ticker}')
        #print(position)
        #print(int(position.qty))
        #print(f'position qty is less than or equal to order qty: {int(position.qty) <= qty}')
        #print(f'position qty is greater than order qty: {int(position.qty) > qty}')
        #print(f'open order qty minus order qty is less than or equal to 0: {int(open_order_qty) - qty <= 0}')
        #print(f'open order qty minus order qty is greater than 0: {int(open_order_qty) - qty > 0}')

        if position is not None and int(position.qty) == open_order_qty and side == 'sell':
            print(f'Error: User: {user} - There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.')
            return f'Error: There are already {open_order_ticker_count} Open Orders totaling {open_order_qty} shares of {ticker}. You have nothing to sell.', 400
        elif position is not None and int(position.qty) <= qty:
            if int(open_order_qty) - qty == 0 and side == 'sell':
                print(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}')
                return f'Error: There is already an Open order to sell {open_order_qty} of {ticker}', 400
    
            elif int(open_order_qty) - qty > 0 and side == 'sell':
                print(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {int(open_order_qty) - qty} leftover.')
        elif position is not None and int(position.qty) > qty:
            if int(open_order_qty) - qty == 0 and side == 'sell':
                print(f'Error: User: {user} - There is already an Open order to sell {open_order_qty} of {ticker}.')
                return f'Error: There is already an Open order to sell {open_order_qty} of {ticker}.', 400
            elif int(open_order_qty) - qty > 0 and side == 'sell':
                print(f'Warning: User: {user} - You are selling {open_order_qty} of {ticker}, which would leave {abs(int(open_order_qty) - qty)} leftover.')
        
        # Order Flow
        if buying_power > 0 and side == 'buy':
            if qty > 0 and math.floor(buying_power // qty) > 0:
                # Submit Order with Stop Loss
                if stop is not None:
                    try:
                        order = api.submit_order(
                            symbol=ticker,
                            qty=qty,
                            side=side,
                            type=order_type,
                            time_in_force=time_in_force,
                            limit_price=limit_price,
                            client_order_id=order_id,
                            order_class='oto',
                            stop_loss={'stop_price': stop }
                        )
                    except tradeapi.rest.APIError as e:
                        if e == 'account is not authorized to trade':
                            print(f'Error: {e} - Check your API Keys exist')
                            return f'Error: {e} - Check your API Keys exist', 400
                        else:
                            print(e)
                            return f'{e}', 400
                else:
                    print(f'Error: User: No Stop Loss was given. Stop Loss is required.')
                    return f'Error: No Stop Loss was given. Stop Loss is required.', 400
                print(order)
                if order.status == 'accepted':
                    print (f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')

                    # Check that order if filled
                    #watchOrderFilledStatus(order_id)

                    return f'Success: Order to {side} of {qty} shares of {ticker}  at ${limit_price} was {order.status}', 200
                else:
                    print(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')
                    return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 400
            else:
                print(f'Error: User: {user} - Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}')
                return f'Error: Not enough Buying Power (${buying_power}) to buy {qty} shares of {ticker} at limit price ${limit_price}', 400
        elif int(position.qty) > 0 and side == 'sell':
            if int(qty) <= int(position.qty):
            # Submit Order with Stop Loss
                if stop is not None:
                    try:
                        order = api.submit_order(
                            symbol=ticker,
                            qty=qty,
                            side=side,
                            type=order_type,
                            time_in_force=time_in_force,
                            limit_price=limit_price,
                            client_order_id=order_id,
                            order_class='oto',
                            stop_loss={'stop_price': stop }
                        )
                    except tradeapi.rest.APIError as e:
                        if e == 'account is not authorized to trade':
                            print(f'Error: {e} - Check your API Keys exist')
                            return f'Error: {e} - Check your API Keys exist', 400
                        else:
                            print(e)
                            return f'{e}', 400
                else:
                    print(f'Error: User: No Stop Loss was given. Stop Loss is required.')
                    return f'Error: No Stop Loss was given. Stop Loss is required.', 400
                print(order)
                if order.status == 'accepted':
                    print (f'Success: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')

                    # Check that order if filled
                    #watchOrderFilledStatus(order_id)

                    return f'Success: Order to {side} of {qty} shares of {ticker}  at ${limit_price} was {order.status}', 200
                else:
                    print(f'Error: User: {user} - Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}')
                    return f'Error: Order to {side} of {qty} shares of {ticker} at ${limit_price} was {order.status}', 400
            else:
                print(f'Error: User: {user} - You cannot sell {qty} when you only have {position.qty}')
                return f'Error: You cannot sell {qty} when you only have {position.qty}', 400
        print(f'Error: User: {user} - You have no Buying Power: ${buying_power}')
        return f'Error: You have no Buying Power: ${buying_power}', 400
    else:
        print(f'Error: User {user} - Data Payload was empty!')
        return f'Error: User {user} - Data Payload was empty!', 400 

if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
